import cv2
import torch
import numpy as np
import torch.nn as nn

from typing import List, Tuple, Dict, Optional, Union, Generator

import utils


def chunks(lst: List, size: Optional[int] = None) -> Union[List, Generator]:
    if size is None:
        yield lst
    else:
        for i in range(0, len(lst), size):
            yield lst[i:i + size]


class Predictor(nn.Module):
    def __init__(self,
                 model_config: Dict = None,
                 classes: Dict = {0: None},
                 weight_path: Optional[str] = None,
                 image_size: Tuple[int, int] = (224, 224),
                 mean: Optional[Tuple[float, float, float]] = None,
                 std: Optional[Tuple[float, float, float]] = None,
                 batch_size: Optional[int] = None,
                 device: str = 'cpu') -> None:
        super(Predictor, self).__init__()
        self.std = std
        self.mean = mean
        self.device = device
        self.classes = classes
        self.image_size = image_size
        self.batch_size = batch_size

        if (self.mean is not None) and (self.std is not None):
            self.mean = torch.tensor(mean, dtype=torch.float).view(1, 3, 1, 1)
            self.std = torch.tensor(std, dtype=torch.float).view(1, 3, 1, 1)

        self.model = utils.create_instance(model_config)
        if weight_path is not None:
            self.model.load_state_dict(torch.load(f=utils.abs_path(weight_path), map_location='cpu'))
        self.model.to(self.device).eval()

    def preprocess(self, images: List[np.ndarray]) -> List[np.ndarray]:
        samples = [cv2.resize(image, dsize=self.image_size) for image in images]
        if (self.mean is not None) and (self.std is not None):
            samples = [cv2.cvtColor(sample, cv2.COLOR_BGR2RGB) for sample in samples]

        return samples

    def process(self, samples: List[np.ndarray]) -> List[torch.Tensor]:
        preds = []
        for batch in chunks(samples, size=self.batch_size):
            batch = [torch.from_numpy(sample) for sample in batch]
            batch = torch.stack(batch, dim=0).to(self.device)
            batch = batch.permute(0, 3, 1, 2).contiguous().float()
            if (self.mean is not None) and (self.std is not None):
                batch = (batch.div(255.) - self.mean) / self.std
            else:
                batch = (batch - batch.mean()) / batch.std()

            with torch.no_grad():
                preds += torch.split(self.model(batch), split_size_or_sections=1, dim=0)

        return preds

    def postprocess(self, preds: List[torch.Tensor]) -> List[Tuple[str, float]]:
        preds = [pred.softmax(dim=1).squeeze(dim=0) for pred in preds]
        preds = [(self.classes[pred.argmax().item()], pred[pred.argmax().item()].item()) for pred in preds]

        return preds

    def forward(self, images: List[np.ndarray]) -> List[Tuple[str, float]]:
        outputs = self.preprocess(images)
        outputs = self.process(outputs)
        outputs = self.postprocess(outputs)

        return outputs

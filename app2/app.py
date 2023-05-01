import torch
from torchvision.models.resnet import ResNet, Bottleneck
from potassium import Potassium, Request, Response

import torch
import torch.nn as nn


class LargeResNet(nn.Module):
    def __init__(self):
        super().__init__()

        self.conv1 = nn.Conv2d(3, 64, kernel_size=7, stride=2, padding=3, bias=False)
        self.bn1 = nn.BatchNorm2d(64)
        self.relu = nn.ReLU(inplace=True)
        self.maxpool = nn.MaxPool2d(kernel_size=3, stride=2, padding=1)

        nthPower = 15
        for i in range(nthPower):
            setattr(self, f"layer{i}", self._make_layer(2**i, 3, stride=1))
        self.avgpool = nn.AdaptiveAvgPool2d((1, 1))
        self.fc = nn.Linear(2**nthPower, 1000)

    def _make_layer(self, planes, blocks, stride=1):
        downsample = None
        if stride != 1 or planes != 64:
            downsample = nn.Sequential(
                nn.Conv2d(64, planes, kernel_size=1, stride=stride, bias=False),
                nn.BatchNorm2d(planes),
            )

        layers = []
        layers.append(Bottleneck(64, planes, stride, downsample))
        for _ in range(1, blocks):
            layers.append(Bottleneck(planes, planes))

        return nn.Sequential(*layers)

    def forward(self, x):
        x = self.conv1(x)
        x = self.bn1(x)
        x = self.relu(x)
        x = self.maxpool(x)

        x = self.layer1(x)
        x = self.layer2(x)
        x = self.layer3(x)
        x = self.layer4(x)

        x = self.avgpool(x)
        x = torch.flatten(x, 1)
        x = self.fc(x)

        return x


class Bottleneck(nn.Module):
    def __init__(self, in_planes, planes, stride=1, downsample=None):
        super().__init__()
        self.conv1 = nn.Conv2d(in_planes, planes, kernel_size=1, bias=False)
        self.bn1 = nn.BatchNorm2d(planes)
        self.conv2 = nn.Conv2d(planes, planes, kernel_size=3, stride=stride, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(planes)
        self.conv3 = nn.Conv2d(planes, 4 * planes, kernel_size=1, bias=False)
        self.bn3 = nn.BatchNorm2d(4 * planes)
        self.relu = nn.ReLU(inplace=True)
        self.downsample = downsample
        self.stride = stride

    def forward(self, x):
        identity = x

        out = self.conv1(x)
        out = self.bn1(out)
        out = self.relu(out)

        out = self.conv2(out)
        out = self.bn2(out)
        out = self.relu(out)

        out = self.conv3(out)
        out = self.bn3(out)

        if self.downsample is not None:
            identity = self.downsample(x)

        out += identity
        out = self.relu(out)

        return out

app = Potassium("large_model_app")

@app.init
def init():
    # Initialize the model and move it to the GPU if available
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = LargeResNet().to(device)
    
    context = {
        "model": model,
    }
    
    return context

@app.handler()
def handler(context: dict, request: Request) -> Response:
    # Perform inference on the input image using the loaded model
    input_image = request.files.get("image")
    model = context.get("model")
    with torch.no_grad():
        output = model(input_image)
    predicted_class = torch.argmax(output).item()

    return Response(
        json = {"predicted_class": predicted_class},
        status = 200
    )

if __name__ == "__main__":
    app.serve()

import os

import pytest
import torch
from torch import tensor

from litdata.streaming import CombinedStreamingDataset, StreamingDataLoader
from litdata.streaming import dataloader as streaming_dataloader_module


class TestStatefulDataset:
    def __init__(self, size, step):
        self.size = size
        self.step = step
        self.counter = 0
        self.shuffle = None

    def set_shuffle(self, shuffle):
        self.shuffle = shuffle

    def __len__(self):
        return self.size

    def __iter__(self):
        self.counter = 0
        return self

    def __next__(self):
        if self.counter == self.size:
            raise StopIteration
        value = self.step * self.counter
        self.counter += 1
        return value

    def state_dict(self, *args, **kwargs):
        return {"counter": self.counter}

    def load_state_dict(self, state_dict):
        self.counter = state_dict["counter"]

    def set_epoch(self, current_epoch):
        pass


class TestCombinedStreamingDataset(CombinedStreamingDataset):
    def _check_datasets(self, datasets) -> None:
        pass


def test_streaming_dataloader():
    dataset = TestCombinedStreamingDataset(
        [TestStatefulDataset(10, 1), TestStatefulDataset(10, -1)], 42, weights=(0.5, 0.5)
    )
    dataloader = StreamingDataLoader(dataset, batch_size=2)
    dataloader_iter = iter(dataloader)
    batches = []
    for batch in dataloader_iter:
        batches.append(batch)

    expected = [
        tensor([0, 0]),
        tensor([1, 2]),
        tensor([-1, -2]),
        tensor([-3, 3]),
        tensor([4, 5]),
        tensor([6, -4]),
        tensor([7, 8]),
        tensor([-5, -6]),
        tensor([9, -7]),
        tensor([-8]),
    ]

    for exp, gen in zip(expected, batches):
        assert torch.equal(exp, gen)

    assert dataloader.state_dict() == {
        "dataset": {"0": {"counter": 10}, "1": {"counter": 9}},
        "current_epoch": 0,
        "latest_worker_idx": 0,
        "num_samples_yielded": {0: [11, 9]},
    }


@pytest.mark.parametrize("profile", [2, True])
def test_dataloader_profiling(profile, tmpdir, monkeypatch):
    monkeypatch.setattr(streaming_dataloader_module, "_VIZ_TRACKER_AVAILABLE", True)

    dataset = TestCombinedStreamingDataset(
        [TestStatefulDataset(10, 1), TestStatefulDataset(10, -1)], 42, weights=(0.5, 0.5)
    )
    dataloader = StreamingDataLoader(
        dataset, batch_size=2, profile_batches=profile, profile_dir=str(tmpdir), num_workers=1
    )
    dataloader_iter = iter(dataloader)
    batches = []
    for batch in dataloader_iter:
        batches.append(batch)

    assert os.path.exists(os.path.join(tmpdir, "result.json"))


def test_dataloader_shuffle():
    dataset = TestCombinedStreamingDataset(
        [TestStatefulDataset(10, 1), TestStatefulDataset(10, -1)], 42, weights=(0.5, 0.5)
    )
    assert dataset._datasets[0].shuffle is None
    assert dataset._datasets[1].shuffle is None
    StreamingDataLoader(dataset, batch_size=2, num_workers=1, shuffle=True)
    assert dataset._datasets[0].shuffle
    assert dataset._datasets[1].shuffle

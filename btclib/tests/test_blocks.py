#!/usr/bin/env python3

# Copyright (C) 2020 The btclib developers
#
# This file is part of btclib. It is subject to the license terms in the
# LICENSE file found in the top-level directory of this distribution.
#
# No part of btclib including this file, may be copied, modified, propagated,
# or distributed except according to the terms contained in the LICENSE file.

"Tests for `btclib.blocks` module."

import json
from datetime import datetime, timezone
from os import path

import pytest

from btclib.blocks import Block, BlockHeader
from btclib.exceptions import BTClibValueError
from btclib.network import NETWORKS

datadir = path.join(path.dirname(__file__), "generated_files")


def test_block_1() -> None:
    "Test first block after genesis"

    fname = "block_1.bin"
    filename = path.join(path.dirname(__file__), "test_data", fname)
    with open(filename, "rb") as file_:
        block_bytes = file_.read()

    block = Block.deserialize(block_bytes)
    assert len(block.transactions) == 1
    assert block.serialize() == block_bytes

    assert block.size == 215
    assert block.weight == 536

    header = block.header
    assert header.version == 1
    assert header.previous_block_hash == NETWORKS["mainnet"].genesis_block
    merkle_root = "0e3e2357e806b6cdb1f70b54c3a3a17b6714ee1f0e68bebb44a74b1efd512098"
    assert header.merkle_root.hex() == merkle_root
    timestamp = datetime(2009, 1, 9, 2, 54, 25, tzinfo=timezone.utc)
    assert header.time == timestamp
    assert header.bits.hex() == "1d00ffff"
    assert header.nonce == 0x9962E301

    hash_ = "00000000839a8e6886ab5951d76f411475428afc90947ee320161bbf18eb6048"
    assert header.hash().hex() == hash_
    assert header.difficulty == 1


def test_exceptions() -> None:

    fname = "block_1.bin"
    filename = path.join(path.dirname(__file__), "test_data", fname)
    with open(filename, "rb") as file_:
        block_bytes = file_.read()

    header_bytes = block_bytes[:68]  # no timestamp
    with pytest.raises(BTClibValueError, match="invalid timestamp "):
        BlockHeader.deserialize(header_bytes)

    header_bytes = block_bytes[:74]  # bits is missing two bytes
    with pytest.raises(BTClibValueError, match="invalid bits: "):
        BlockHeader.deserialize(header_bytes)

    header_bytes = block_bytes[:76]  # nonce is missing
    with pytest.raises(BTClibValueError, match="invalid nonce: "):
        BlockHeader.deserialize(header_bytes)

    with pytest.raises(IndexError, match="list index out of range"):
        Block.deserialize(block_bytes[:80] + b"\xff")

    header_bytes = block_bytes[:80]

    header = BlockHeader.deserialize(header_bytes)
    header.version = 0
    with pytest.raises(BTClibValueError, match="invalid version: "):
        header.assert_valid()
    header.version = 0x7FFFFFFF + 1
    with pytest.raises(BTClibValueError, match="invalid version: "):
        header.assert_valid()

    header = BlockHeader.deserialize(header_bytes)
    header.previous_block_hash = b"\xff" * 33
    with pytest.raises(BTClibValueError, match="invalid previous block hash: "):
        header.assert_valid()

    header = BlockHeader.deserialize(header_bytes)
    header.merkle_root = b"\xff" * 33
    with pytest.raises(BTClibValueError, match="invalid merkle root: "):
        header.assert_valid()

    header = BlockHeader.deserialize(header_bytes)
    header.bits = b"\xff" * 5
    with pytest.raises(BTClibValueError, match="invalid bits: "):
        header.assert_valid()

    header = BlockHeader.deserialize(header_bytes)
    # one second before genesis
    header.time = datetime(2009, 1, 3, 18, 15, 4, tzinfo=timezone.utc)
    err_msg = "invalid timestamp \\(before genesis\\): "
    with pytest.raises(BTClibValueError, match=err_msg):
        header.assert_valid()

    header = BlockHeader.deserialize(header_bytes)
    header.nonce = 0
    with pytest.raises(BTClibValueError, match="invalid nonce: "):
        header.assert_valid()

    header = BlockHeader.deserialize(header_bytes)
    header.nonce += 1
    with pytest.raises(BTClibValueError, match="invalid proof-of-work: "):
        header.assert_valid()


def test_block_170() -> None:
    "Test first block with a transaction"

    fname = "block_170.bin"
    filename = path.join(path.dirname(__file__), "test_data", fname)
    with open(filename, "rb") as file_:
        block_bytes = file_.read()

    block = Block.deserialize(block_bytes)
    assert len(block.transactions) == 2
    assert block.serialize() == block_bytes

    assert block.size == 490
    assert block.weight == 1636

    header = block.header
    assert header.version == 1
    prev_block = "000000002a22cfee1f2c846adbd12b3e183d4f97683f85dad08a79780a84bd55"
    assert header.previous_block_hash.hex() == prev_block
    merkle_root = "7dac2c5666815c17a3b36427de37bb9d2e2c5ccec3f8633eb91a4205cb4c10ff"
    assert header.merkle_root.hex() == merkle_root
    timestamp = datetime(2009, 1, 12, 3, 30, 25, tzinfo=timezone.utc)
    assert header.time == timestamp
    assert header.bits.hex() == "1d00ffff"
    assert header.nonce == 0x709E3E28

    hash_ = "00000000d1145790a8694403d4063f323d499e655c83426834d4ce2f8dd4a2ee"
    assert header.hash().hex() == hash_
    assert header.difficulty == 1


def test_block_200000() -> None:

    fname = "block_200000.bin"
    filename = path.join(path.dirname(__file__), "test_data", fname)
    with open(filename, "rb") as file_:
        block_bytes = file_.read()

    block = Block.deserialize(block_bytes)
    assert len(block.transactions) == 388
    assert block.serialize() == block_bytes

    assert block.size == 247533
    assert block.weight == 989800

    header = block.header
    assert header.version == 2
    prev_block = "00000000000003a20def7a05a77361b9657ff954b2f2080e135ea6f5970da215"
    assert header.previous_block_hash.hex() == prev_block
    merkle_root = "a08f8101f50fd9c9b3e5252aff4c1c1bd668f878fffaf3d0dbddeb029c307e88"
    assert header.merkle_root.hex() == merkle_root
    assert header.time == datetime(2012, 9, 22, 10, 45, 59, tzinfo=timezone.utc)
    assert header.bits.hex() == "1a05db8b"
    assert header.nonce == 0xF7D8D840

    hash_ = "000000000000034a7dedef4a161fa058a2d67a173a90155f3a2fe6fc132e0ebf"
    assert header.hash().hex() == hash_
    assert 0 <= header.difficulty - 2_864_140 < 1

    block.transactions.pop()
    err_msg = "invalid merkle root: "
    with pytest.raises(BTClibValueError, match=err_msg):
        block.assert_valid()

    block.transactions.pop(0)
    err_msg = "first transaction is not a coinbase"
    with pytest.raises(BTClibValueError, match=err_msg):
        block.assert_valid()


@pytest.mark.seventh
def test_block_481824() -> None:
    "Test first block with segwit transaction as seen from legacy nodes"

    for i, fname in enumerate(["block_481824.bin", "block_481824_complete.bin"]):
        filename = path.join(path.dirname(__file__), "test_data", fname)
        with open(filename, "rb") as file_:
            block_bytes = file_.read()

        block = Block.deserialize(block_bytes)
        assert len(block.transactions) == 1866
        assert block.serialize() == block_bytes

        header = block.header
        assert header.version == 0x20000002
        prev_block = "000000000000000000cbeff0b533f8e1189cf09dfbebf57a8ebe349362811b80"
        assert header.previous_block_hash.hex() == prev_block
        merkle_root = "6438250cad442b982801ae6994edb8a9ec63c0a0ba117779fbe7ef7f07cad140"
        assert header.merkle_root.hex() == merkle_root
        timestamp = datetime(2017, 8, 24, 1, 57, 37, tzinfo=timezone.utc)
        assert header.time == timestamp
        assert header.bits.hex() == "18013ce9"
        assert header.nonce == 0x2254FF22

        hash_ = "0000000000000000001c8018d9cb3b742ef25114f27563e3fc4a1902167f9893"
        assert header.hash().hex() == hash_
        assert 0 <= header.difficulty - 888_171_856_257 < 1

        if i:  # segwit nodes see the witness data
            assert block.transactions[0].vin[0].txinwitness
            assert block.size == 989_323
            assert block.weight == 3_954_548
        else:  # legacy nodes see NO witness data
            assert not block.transactions[0].vin[0].txinwitness


def test_dataclasses_json_dict() -> None:

    fname = "block_481824.bin"
    filename = path.join(path.dirname(__file__), "test_data", fname)
    with open(filename, "rb") as binfile_:
        block = binfile_.read()

    # dataclass
    block_data = Block.deserialize(block)
    assert isinstance(block_data, Block)

    # dict
    block_dict = block_data.to_dict()
    assert isinstance(block_dict, dict)
    filename = path.join(datadir, "block_481824.json")
    with open(filename, "w") as file_:
        json.dump(block_dict, file_, indent=4)
    assert block_data == Block.from_dict(block_dict)

    # str
    block_json_str = block_data.to_json()
    assert isinstance(block_json_str, str)
    assert block_data == Block.from_json(block_json_str)

    block_header = block_data.header.serialize()

    # dataclass
    block_header_data = BlockHeader.deserialize(block_header)
    assert isinstance(block_header_data, BlockHeader)

    # dict
    block_header_d = block_header_data.to_dict()
    assert isinstance(block_header_d, dict)
    filename = path.join(datadir, "block_header_481824.json")
    with open(filename, "w") as file_:
        json.dump(block_header_d, file_, indent=4)
    assert block_header_data == BlockHeader.from_dict(block_header_d)

    # str
    block_header_s = block_header_data.to_json()
    assert isinstance(block_header_s, str)
    assert block_header_data == BlockHeader.from_json(block_header_s)

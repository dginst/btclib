#!/usr/bin/env python3

# Copyright (C) 2020 The btclib developers
#
# This file is part of btclib. It is subject to the license terms in the
# LICENSE file found in the top-level directory of this distribution.
#
# No part of btclib including this file, may be copied, modified, propagated,
# or distributed except according to the terms contained in the LICENSE file.

from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Type, TypeVar, Optional, Union
from base64 import b64decode, b64encode
from copy import deepcopy

from .tx import Tx
from .tx_in import witness_serialize, witness_deserialize
from .tx_out import TxOut
from .alias import Token
from .utils import hash160, sha256
from .scriptpubkey import payload_from_scriptPubKey
from . import varint, script


_PsbtInput = TypeVar("_PsbtInput", bound="PsbtInput")


@dataclass
class PsbtInput:
    non_witness_utxo: Optional[Tx] = None
    witness_utxo: Optional[TxOut] = None
    partial_sigs: Dict[str, str] = field(default_factory=dict)
    sighash: Optional[int] = 0
    redeem_script: List[Token] = field(default_factory=list)
    witness_script: List[Token] = field(default_factory=list)
    hd_keypaths: List[Dict[str, str]] = field(default_factory=list)
    final_script_sig: List[Token] = field(default_factory=list)
    final_script_witness: List[str] = field(default_factory=list)
    por_commitment: Optional[str] = None
    proprietary: Dict[int, Dict[str, str]] = field(default_factory=dict)
    unknown: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def decode(cls: Type[_PsbtInput], input_map: Dict[bytes, bytes]) -> _PsbtInput:
        non_witness_utxo = None
        witness_utxo = None
        partial_sigs = {}
        sighash = 0
        redeem_script = []
        witness_script = []
        hd_keypaths = []
        final_script_sig = []
        final_script_witness = []
        por_commitment = None
        proprietary: Dict[int, Dict[str, str]] = {}
        unknown = {}
        for key, value in input_map.items():
            if key[0] == 0x00:
                assert len(key) == 1
                non_witness_utxo = Tx.deserialize(value)
            elif key[0] == 0x01:
                assert len(key) == 1
                witness_utxo = TxOut.deserialize(value)
            elif key[0] == 0x02:
                assert len(key) == 33 + 1
                partial_sigs[key[1:].hex()] = value.hex()
            elif key[0] == 0x03:
                assert len(key) == 1
                assert len(value) == 4
                sighash = int.from_bytes(value, "little")
            elif key[0] == 0x04:
                assert len(key) == 1
                redeem_script = script.decode(value)
            elif key[0] == 0x05:
                assert len(key) == 1
                witness_script = script.decode(value)
            elif key[0] == 0x06:
                assert len(key) == 33 + 1
                assert len(value) % 4 == 0
                hd_keypaths.append(
                    {
                        "xpub": key[1:].hex(),
                        "fingerprint": value[:4].hex(),
                        "derivation_path": value[4:].hex(),
                    }
                )
            elif key[0] == 0x07:
                assert len(key) == 1
                final_script_sig = script.decode(value)
            elif key[0] == 0x08:
                assert len(key) == 1
                final_script_witness = witness_deserialize(value)
                pass
            elif key[0] == 0x09:
                assert len(key) == 1
                por_commitment = value.hex()  # TODO: bip127
            elif key[0] == 0xFC:  # proprietary use
                prefix = varint.decode(key[1:])
                if prefix not in proprietary.keys():
                    proprietary[prefix] = {}
                key = key[1 + len(varint.encode(prefix)) :]
                proprietary[prefix][key.hex()] = value.hex()
            else:  # unkown keys
                unknown[key.hex()] = value.hex()

        out = cls(
            non_witness_utxo=non_witness_utxo,
            witness_utxo=witness_utxo,
            partial_sigs=partial_sigs,
            sighash=sighash,
            redeem_script=redeem_script,
            witness_script=witness_script,
            hd_keypaths=hd_keypaths,
            final_script_sig=final_script_sig,
            final_script_witness=final_script_witness,
            por_commitment=por_commitment,
            proprietary=proprietary,
            unknown=unknown,
        )

        out.assert_valid()

        return out

    def serialize(self) -> bytes:
        out = b""
        if self.non_witness_utxo:
            out += b"\x01\x00"
            utxo = self.non_witness_utxo.serialize()
            out += varint.encode(len(utxo)) + utxo
        if self.witness_utxo:
            out += b"\x01\x01"
            utxo = self.witness_utxo.serialize()
            out += varint.encode(len(utxo)) + utxo
        if self.partial_sigs:
            for key, value in self.partial_sigs.items():
                out += b"\x22\x02" + bytes.fromhex(key)
                out += varint.encode(len(value) // 2) + bytes.fromhex(value)
        if self.sighash:
            out += b"\x01\x03\x04"
            out += self.sighash.to_bytes(4, "little")
        if self.redeem_script:
            out += b"\x01\x04"
            out += script.serialize(self.redeem_script)
        if self.witness_script:
            out += b"\x01\x05"
            out += script.serialize(self.witness_script)
        if self.hd_keypaths:
            for hd_keypath in self.hd_keypaths:
                out += b"\x22\x06" + bytes.fromhex(hd_keypath["xpub"])
                keypath = bytes.fromhex(hd_keypath["fingerprint"])
                keypath += bytes.fromhex(hd_keypath["derivation_path"])
                out += varint.encode(len(keypath)) + keypath
        if self.final_script_sig:
            out += b"\x01\x07"
            out += script.serialize(self.final_script_sig)
        if self.final_script_witness:
            out += b"\x01\x08"
            wit = witness_serialize(self.final_script_witness)
            out += varint.encode(len(wit)) + wit
        if self.por_commitment:  # TODO
            out += b"\x01\x09"
            c = bytes.fromhex(self.por_commitment)
            out += varint.encode(len(c)) + c
        if self.proprietary:
            for (owner, dictionary) in self.proprietary.items():
                for key, value in dictionary.items():
                    key_bytes = b"\xfc" + varint.encode(owner) + bytes.fromhex(key)
                    out += varint.encode(len(key_bytes)) + key_bytes
                    out += varint.encode(len(value) // 2) + bytes.fromhex(value)
        if self.unknown:
            for key, value in self.unknown.items():
                out += varint.encode(len(key) // 2) + bytes.fromhex(key)
                out += varint.encode(len(value) // 2) + bytes.fromhex(value)
        return out

    def assert_valid(self) -> None:
        pass


_PsbtOutput = TypeVar("_PsbtOutput", bound="PsbtOutput")


@dataclass
class PsbtOutput:
    redeem_script: List[Token] = field(default_factory=list)
    witness_script: List[Token] = field(default_factory=list)
    hd_keypaths: List[Dict[str, str]] = field(default_factory=list)
    proprietary: Dict[int, Dict[str, str]] = field(default_factory=dict)
    unknown: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def decode(cls: Type[_PsbtOutput], output_map: Dict[bytes, bytes]) -> _PsbtOutput:
        redeem_script = []
        witness_script = []
        hd_keypaths = []
        proprietary: Dict[int, Dict[str, str]] = {}
        unknown = {}
        for key, value in output_map.items():
            if key[0] == 0x00:
                assert len(key) == 1
                redeem_script = script.decode(value)
            elif key[0] == 0x01:
                assert len(key) == 1
                witness_script = script.decode(value)
            elif key[0] == 0x02:
                assert len(key) == 33 + 1
                assert len(value) % 4 == 0
                hd_keypaths.append(
                    {
                        "xpub": key[1:].hex(),
                        "fingerprint": value[:4].hex(),
                        "derivation_path": value[4:].hex(),
                    }
                )
            elif key[0] == 0xFC:  # proprietary use
                prefix = varint.decode(key[1:])
                if prefix not in proprietary.keys():
                    proprietary[prefix] = {}
                key = key[1 + len(varint.encode(prefix)) :]
                proprietary[prefix][key.hex()] = value.hex()
            else:  # unkown keys
                unknown[key.hex()] = value.hex()

        out = cls(
            redeem_script=redeem_script,
            witness_script=witness_script,
            hd_keypaths=hd_keypaths,
            proprietary=proprietary,
            unknown=unknown,
        )

        out.assert_valid()

        return out

    def serialize(self) -> bytes:
        out = b""
        if self.redeem_script:
            out += b"\x01\x00"
            out += script.serialize(self.redeem_script)
        if self.witness_script:
            out += b"\x01\x01"
            out += script.serialize(self.witness_script)
        if self.hd_keypaths:
            for hd_keypath in self.hd_keypaths:
                out += b"\x22\x02" + bytes.fromhex(hd_keypath["xpub"])
                keypath = bytes.fromhex(hd_keypath["fingerprint"])
                keypath += bytes.fromhex(hd_keypath["derivation_path"])
                out += varint.encode(len(keypath)) + keypath
        if self.proprietary:
            for (owner, dictionary) in self.proprietary.items():
                for key, value in dictionary.items():
                    key_bytes = b"\xfc" + varint.encode(owner) + bytes.fromhex(key)
                    out += varint.encode(len(key_bytes)) + key_bytes
                    out += varint.encode(len(value) // 2) + bytes.fromhex(value)
        if self.unknown:
            for key, value in self.unknown.items():
                out += varint.encode(len(key) // 2) + bytes.fromhex(key)
                out += varint.encode(len(value) // 2) + bytes.fromhex(value)
        return out

    def assert_valid(self) -> None:
        pass


_PSbt = TypeVar("_PSbt", bound="Psbt")


@dataclass
class Psbt:
    tx: Tx
    inputs: List[PsbtInput]
    outputs: List[PsbtOutput]
    version: Optional[int] = 0
    hd_keypaths: List[Dict[str, str]] = field(default_factory=list)
    proprietary: Dict[int, Dict[str, str]] = field(default_factory=dict)
    unknown: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def deserialize(cls: Type[_PSbt], string: str) -> _PSbt:
        data = b64decode(string)

        magic_bytes = data[:5]
        assert magic_bytes == b"psbt\xff", "Malformed psbt: missing magic bytes"

        data = data[5:]

        global_map, data = deserialize_map(data)
        version = 0
        # xpub = None
        hd_keypaths = []
        proprietary: Dict[int, Dict[str, str]] = {}
        unknown = {}
        for key, value in global_map.items():
            if key[0] == 0x00:
                assert len(key) == 1
                tx = Tx.deserialize(value)
            elif key[0] == 0x01:  # TODO
                assert len(key) == 78 + 1
                assert len(value) % 4 == 0
                hd_keypaths.append(
                    {
                        "xpub": key[1:].hex(),
                        "fingerprint": value[:4].hex(),
                        "derivation_path": value[4:].hex(),
                    }
                )
            elif key[0] == 0xFB:
                assert len(value) == 4
                version = int.from_bytes(value, "little")
            elif key[0] == 0xFC:
                prefix = varint.decode(key[1:])
                if prefix not in proprietary.keys():
                    proprietary[prefix] = {}
                key = key[1 + len(varint.encode(prefix)) :]
                proprietary[prefix][key.hex()] = value.hex()
            else:  # unkown keys
                unknown[key.hex()] = value.hex()

        input_len = len(tx.vin)
        output_len = len(tx.vout)

        inputs = []
        for i in range(input_len):
            input_map, data = deserialize_map(data)
            inputs.append(PsbtInput.decode(input_map))

        outputs = []
        for i in range(output_len):
            output_map, data = deserialize_map(data)
            outputs.append(PsbtOutput.decode(output_map))

        psbt = cls(
            tx=tx,
            inputs=inputs,
            outputs=outputs,
            version=version,
            hd_keypaths=hd_keypaths,
            proprietary=proprietary,
            unknown=unknown,
        )

        psbt.assert_valid()

        return psbt

    def serialize(self) -> str:
        out = bytes.fromhex("70736274ff")
        out += b"\x01\x00"
        tx = self.tx.serialize()
        out += varint.encode(len(tx)) + tx
        if self.hd_keypaths:
            for hd_keypath in self.hd_keypaths:
                out += b"\x4f\x01" + bytes.fromhex(hd_keypath["xpub"])
                keypath = bytes.fromhex(hd_keypath["fingerprint"])
                keypath += bytes.fromhex(hd_keypath["derivation_path"])
                out += varint.encode(len(keypath)) + keypath
        if self.version:
            out += b"\x01\xfb\x04"
            out += self.version.to_bytes(4, "little")
        if self.proprietary:
            for (owner, dictionary) in self.proprietary.items():
                for key, value in dictionary.items():
                    key_bytes = b"\xfc" + varint.encode(owner) + bytes.fromhex(key)
                    out += varint.encode(len(key_bytes)) + key_bytes
                    out += varint.encode(len(value) // 2) + bytes.fromhex(value)
        if self.unknown:
            for key, value in self.unknown.items():
                out += varint.encode(len(key) // 2) + bytes.fromhex(key)
                out += varint.encode(len(value) // 2) + bytes.fromhex(value)
        out += b"\x00"
        for input_map in self.inputs:
            out += input_map.serialize() + b"\x00"
        for output_map in self.outputs:
            out += output_map.serialize() + b"\x00"
        return b64encode(out).decode()

    def assert_valid(self) -> None:
        for vin in self.tx.vin:
            assert vin.scriptSig == []
            assert vin.txinwitness == []
        for input_map in self.inputs:
            input_map.assert_valid()
        for output_map in self.outputs:
            output_map.assert_valid()

        for i, tx_in in enumerate(self.tx.vin):
            if self.inputs[i].non_witness_utxo:
                txid = tx_in.prevout.hash
                assert self.inputs[i].non_witness_utxo.txid == txid
                scriptPubKey = (
                    self.inputs[i].non_witness_utxo.vout[tx_in.prevout.n].scriptPubKey
                )
            elif self.inputs[i].witness_utxo:
                scriptPubKey = self.inputs[i].witness_utxo.scriptPubKey

            if self.inputs[i].redeem_script:
                hash = hash160(script.encode(self.inputs[i].redeem_script))
                assert hash == payload_from_scriptPubKey(scriptPubKey)[1]

            if self.inputs[i].witness_script:
                if self.inputs[i].non_witness_utxo:
                    scriptPubKey = (
                        self.inputs[i]
                        .non_witness_utxo.vout[tx_in.prevout.n]
                        .scriptPubKey
                    )
                elif self.inputs[i].witness_utxo:
                    scriptPubKey = self.inputs[i].witness_utxo.scriptPubKey
                if self.inputs[i].redeem_script:
                    scriptPubKey = self.inputs[i].redeem_script

                hash = sha256(script.encode(self.inputs[i].witness_script))
                assert hash == payload_from_scriptPubKey(scriptPubKey)[1], (
                    self.inputs[i].witness_script,
                    hash,
                    scriptPubKey,
                    payload_from_scriptPubKey(scriptPubKey),
                )


def deserialize_map(data: bytes) -> Tuple[Dict[bytes, bytes], bytes]:
    assert len(data) != 0, "Malformed psbt: at least a map is missing"
    partial_map: Dict[bytes, bytes] = {}
    while True:
        if data[0] == 0:
            data = data[1:]
            return partial_map, data
        key_len = varint.decode(data)
        data = data[len(varint.encode(key_len)) :]
        key = data[:key_len]
        data = data[key_len:]
        value_len = varint.decode(data)
        data = data[len(varint.encode(value_len)) :]
        value = data[:value_len]
        data = data[value_len:]
        assert key not in partial_map.keys(), "Malformed psbt: duplicate keys"
        partial_map[key] = value


def psbt_from_tx(tx: Tx) -> Psbt:
    tx = deepcopy(tx)
    for input in tx.vin:
        input.scriptSig = []
        input.txinwitness = []
    inputs = [PsbtInput() for _ in tx.vin]
    outputs = [PsbtOutput() for _ in tx.vout]
    return Psbt(tx=tx, inputs=inputs, outputs=outputs, unknown={})


def _combine(
    maps: Union[List[PsbtInput], List[PsbtOutput]]
) -> Union[PsbtOutput, PsbtInput]:
    out = maps[0]
    for psbt_map in maps[1:]:
        for key in psbt_map.__dict__:

            if isinstance(getattr(psbt_map, key), dict):
                if getattr(out, key):
                    getattr(out, key).update(getattr(psbt_map, key))
                else:
                    setattr(out, key, getattr(psbt_map, key))

            elif isinstance(getattr(psbt_map, key), list):
                if getattr(out, key):
                    for x in getattr(psbt_map, key):
                        if x not in getattr(out, key):
                            getattr(out, key).append(x)
                else:
                    setattr(out, key, getattr(psbt_map, key))

            elif getattr(psbt_map, key):
                if getattr(out, key):
                    assert getattr(psbt_map, key) == getattr(out, key), key
                else:
                    setattr(out, key, getattr(psbt_map, key))
    out.assert_valid()
    return out


def combine_psbts(psbts: List[Psbt]) -> Psbt:
    final_psbt = psbts[0]
    txid = psbts[0].tx.txid
    for psbt in psbts[1:]:
        assert psbt.tx.txid == txid

    inputs = [
        _combine([psbt.inputs[x] for psbt in psbts]) for x in range(len(psbt.inputs))
    ]
    psbt.inputs = inputs

    outputs = [
        _combine([psbt.outputs[x] for psbt in psbts]) for x in range(len(psbt.outputs))
    ]
    final_psbt.outputs = outputs

    for psbt in psbts:
        if final_psbt.unknown:
            final_psbt.unknown.update(psbt.unknown)
        else:
            final_psbt.unknown = psbt.unknown

    return final_psbt


def finalize_psbt(psbt: Psbt) -> Psbt:
    psbt = deepcopy(psbt)
    for psbt_in in psbt.inputs:
        assert psbt_in.partial_sigs
        if psbt_in.witness_script:
            psbt_in.final_script_sig = [
                script.encode(psbt_in.redeem_script).hex().upper()
            ]
            psbt_in.final_script_witness = list(psbt_in.partial_sigs.values())
            psbt_in.final_script_witness += [
                script.encode(psbt_in.witness_script).hex()
            ]
            if len(psbt_in.partial_sigs) > 1:
                psbt_in.final_script_witness = [""] + psbt_in.final_script_witness
        else:
            psbt_in.final_script_sig = [
                a.upper() for a in list(psbt_in.partial_sigs.values())
            ]
            psbt_in.final_script_sig += [
                script.encode(psbt_in.redeem_script).hex().upper()
            ]
            if len(psbt_in.partial_sigs) > 1:
                psbt_in.final_script_sig = [0] + psbt_in.final_script_sig
        psbt_in.partial_sigs = {}
        psbt_in.sighash = 0
        psbt_in.redeem_script = []
        psbt_in.witness_script = []
        psbt_in.hd_keypaths = []
        psbt_in.por_commitment = None
    return psbt


def extract_tx(psbt: Psbt) -> Tx:
    tx = psbt.tx
    for i, vin in enumerate(tx.vin):
        vin.scriptSig = psbt.inputs[i].final_script_sig
        if psbt.inputs[i].final_script_witness:
            vin.txinwitness = psbt.inputs[i].final_script_witness
    return tx

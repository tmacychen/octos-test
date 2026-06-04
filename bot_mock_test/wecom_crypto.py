#!/usr/bin/env python3
"""
WeCom (企业微信) 加密工具 - 匹配 wecom_crypto.rs 的纯 Rust 实现

用于 mock 服务器中模拟 WeCom 服务器的消息加密和签名。
"""

import hashlib
import struct
from typing import Tuple

# AES-256 S-Box (standard Rijndael)
AES_SBOX = [
    0x63, 0x7c, 0x77, 0x7b, 0xf2, 0x6b, 0x6f, 0xc5, 0x30, 0x01, 0x67, 0x2b, 0xfe, 0xd7, 0xab, 0x76,
    0xca, 0x82, 0xc9, 0x7d, 0xfa, 0x59, 0x47, 0xf0, 0xad, 0xd4, 0xa2, 0xaf, 0x9c, 0xa4, 0x72, 0xc0,
    0xb7, 0xfd, 0x93, 0x26, 0x36, 0x3f, 0xf7, 0xcc, 0x34, 0xa5, 0xe5, 0xf1, 0x71, 0xd8, 0x31, 0x15,
    0x04, 0xc7, 0x23, 0xc3, 0x18, 0x96, 0x05, 0x9a, 0x07, 0x12, 0x80, 0xe2, 0xeb, 0x27, 0xb2, 0x75,
    0x09, 0x83, 0x2c, 0x1a, 0x1b, 0x6e, 0x5a, 0xa0, 0x52, 0x3b, 0xd6, 0xb3, 0x29, 0xe3, 0x2f, 0x84,
    0x53, 0xd1, 0x00, 0xed, 0x20, 0xfc, 0xb1, 0x5b, 0x6a, 0xcb, 0xbe, 0x39, 0x4a, 0x4c, 0x58, 0xcf,
    0xd0, 0xef, 0xaa, 0xfb, 0x43, 0x4d, 0x33, 0x85, 0x45, 0xf9, 0x02, 0x7f, 0x50, 0x3c, 0x9f, 0xa8,
    0x51, 0xa3, 0x40, 0x8f, 0x92, 0x9d, 0x38, 0xf5, 0xbc, 0xb6, 0xda, 0x21, 0x10, 0xff, 0xf3, 0xd2,
    0xcd, 0x0c, 0x13, 0xec, 0x5f, 0x97, 0x44, 0x17, 0xc4, 0xa7, 0x7e, 0x3d, 0x64, 0x5d, 0x19, 0x73,
    0x60, 0x81, 0x4f, 0xdc, 0x22, 0x2a, 0x90, 0x88, 0x46, 0xee, 0xb8, 0x14, 0xde, 0x5e, 0x0b, 0xdb,
    0xe0, 0x32, 0x3a, 0x0a, 0x49, 0x06, 0x24, 0x5c, 0xc2, 0xd3, 0xac, 0x62, 0x91, 0x95, 0xe4, 0x79,
    0xe7, 0xc8, 0x37, 0x6d, 0x8d, 0xd5, 0x4e, 0xa9, 0x6c, 0x56, 0xf4, 0xea, 0x65, 0x7a, 0xae, 0x08,
    0xba, 0x78, 0x25, 0x2e, 0x1c, 0xa6, 0xb4, 0xc6, 0xe8, 0xdd, 0x74, 0x1f, 0x4b, 0xbd, 0x8b, 0x8a,
    0x70, 0x3e, 0xb5, 0x66, 0x48, 0x03, 0xf6, 0x0e, 0x61, 0x35, 0x57, 0xb9, 0x86, 0xc1, 0x1d, 0x9e,
    0xe1, 0xf8, 0x98, 0x11, 0x69, 0xd9, 0x8e, 0x94, 0x9b, 0x1e, 0x87, 0xe9, 0xce, 0x55, 0x28, 0xdf,
    0x8c, 0xa1, 0x89, 0x0d, 0xbf, 0xe6, 0x42, 0x68, 0x41, 0x99, 0x2d, 0x0f, 0xb0, 0x54, 0xbb, 0x16,
]

INV_SBOX = [0] * 256
for i, v in enumerate(AES_SBOX):
    INV_SBOX[v] = i

# Round constants
RCON = [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1b, 0x36]


def _xtime(a: int) -> int:
    """Multiply by x (0x02) in GF(2^8)."""
    return ((a << 1) ^ 0x11b) & 0xff if a & 0x80 else (a << 1) & 0xff


def _gf_mul(a: int, b: int) -> int:
    """Multiply two bytes in GF(2^8)."""
    result = 0
    for _ in range(8):
        if b & 1:
            result ^= a
        hi = a & 0x80
        a = (a << 1) & 0xff
        if hi:
            a ^= 0x1b
        b >>= 1
    return result


def _sub_word(word: int) -> int:
    """Apply S-Box to each byte of a 32-bit word."""
    return (AES_SBOX[(word >> 24) & 0xff] << 24 |
            AES_SBOX[(word >> 16) & 0xff] << 16 |
            AES_SBOX[(word >> 8) & 0xff] << 8 |
            AES_SBOX[word & 0xff])


def _rot_word(word: int) -> int:
    """Rotate 32-bit word left by 8 bits."""
    return ((word << 8) | (word >> 24)) & 0xffffffff


def _key_expansion(key: bytes) -> list:
    """AES-256 key expansion: 32 bytes key → 15 round keys (240 bytes)."""
    # AES-256: 14 rounds, 15 round keys (60 32-bit words)
    nk = 8   # 32 bytes / 4 = 8 words
    nr = 14
    w = [0] * (4 * (nr + 1))

    for i in range(nk):
        w[i] = struct.unpack('>I', key[4*i:4*i+4])[0]

    for i in range(nk, 4 * (nr + 1)):
        temp = w[i - 1]
        if i % nk == 0:
            temp = _sub_word(_rot_word(temp)) ^ (RCON[i // nk - 1] << 24)
        elif i % nk == 4:
            temp = _sub_word(temp)
        w[i] = w[i - nk] ^ temp

    return w


def _add_round_key(state: list, round_key: list):
    """XOR state with round key."""
    for i in range(16):
        state[i] ^= (round_key[i // 4] >> (24 - 8 * (i % 4))) & 0xff


def _sub_bytes(state: list):
    """Apply S-Box substitution."""
    for i in range(16):
        state[i] = AES_SBOX[state[i]]


def _inv_sub_bytes(state: list):
    """Apply inverse S-Box substitution."""
    for i in range(16):
        state[i] = INV_SBOX[state[i]]


def _shift_rows(state: list):
    """Shift rows of the state matrix."""
    s = [0] * 16
    # Row 0: no shift
    s[0], s[1], s[2], s[3] = state[0], state[1], state[2], state[3]
    # Row 1: shift left 1
    s[4], s[5], s[6], s[7] = state[5], state[6], state[7], state[4]
    # Row 2: shift left 2
    s[8], s[9], s[10], s[11] = state[10], state[11], state[8], state[9]
    # Row 3: shift left 3
    s[12], s[13], s[14], s[15] = state[15], state[12], state[13], state[14]
    state[:] = s


def _inv_shift_rows(state: list):
    """Inverse shift rows."""
    s = [0] * 16
    s[0], s[1], s[2], s[3] = state[0], state[1], state[2], state[3]
    s[5], s[6], s[7], s[4] = state[4], state[5], state[6], state[7]
    s[10], s[11], s[8], s[9] = state[8], state[9], state[10], state[11]
    s[15], s[12], s[13], s[14] = state[12], state[13], state[14], state[15]
    state[:] = s


def _mix_columns(state: list):
    """Mix columns of the state matrix."""
    for c in range(4):
        i = c * 4
        a = state[i:i+4]
        state[i]   = _gf_mul(2, a[0]) ^ _gf_mul(3, a[1]) ^ a[2] ^ a[3]
        state[i+1] = a[0] ^ _gf_mul(2, a[1]) ^ _gf_mul(3, a[2]) ^ a[3]
        state[i+2] = a[0] ^ a[1] ^ _gf_mul(2, a[2]) ^ _gf_mul(3, a[3])
        state[i+3] = _gf_mul(3, a[0]) ^ a[1] ^ a[2] ^ _gf_mul(2, a[3])


def _inv_mix_columns(state: list):
    """Inverse mix columns."""
    for c in range(4):
        i = c * 4
        a = state[i:i+4]
        state[i]   = _gf_mul(14, a[0]) ^ _gf_mul(11, a[1]) ^ _gf_mul(13, a[2]) ^ _gf_mul(9, a[3])
        state[i+1] = _gf_mul(9, a[0]) ^ _gf_mul(14, a[1]) ^ _gf_mul(11, a[2]) ^ _gf_mul(13, a[3])
        state[i+2] = _gf_mul(13, a[0]) ^ _gf_mul(9, a[1]) ^ _gf_mul(14, a[2]) ^ _gf_mul(11, a[3])
        state[i+3] = _gf_mul(11, a[0]) ^ _gf_mul(13, a[1]) ^ _gf_mul(9, a[2]) ^ _gf_mul(14, a[3])


def _aes_encrypt_block(block: bytes, round_keys: list) -> bytes:
    """Encrypt a single 16-byte block with AES-256."""
    state = list(block)
    _add_round_key(state, round_keys[0:4])

    for rnd in range(1, 14):
        _sub_bytes(state)
        _shift_rows(state)
        _mix_columns(state)
        _add_round_key(state, round_keys[rnd * 4:(rnd + 1) * 4])

    _sub_bytes(state)
    _shift_rows(state)
    _add_round_key(state, round_keys[14 * 4:15 * 4])

    return bytes(state)


def _aes_decrypt_block(block: bytes, round_keys: list) -> bytes:
    """Decrypt a single 16-byte block with AES-256."""
    state = list(block)
    _add_round_key(state, round_keys[14 * 4:15 * 4])

    for rnd in range(13, 0, -1):
        _inv_shift_rows(state)
        _inv_sub_bytes(state)
        _add_round_key(state, round_keys[rnd * 4:(rnd + 1) * 4])
        _inv_mix_columns(state)

    _inv_shift_rows(state)
    _inv_sub_bytes(state)
    _add_round_key(state, round_keys[0:4])

    return bytes(state)


def aes_256_cbc_encrypt(plaintext: bytes, key: bytes, iv: bytes) -> bytes:
    """AES-256-CBC encrypt using cryptography library."""
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    padded = pkcs7_pad(plaintext, 16)
    cipher = Cipher(algorithms.AES256(key), modes.CBC(iv))
    encryptor = cipher.encryptor()
    return encryptor.update(padded) + encryptor.finalize()


def aes_256_cbc_decrypt(ciphertext: bytes, key: bytes, iv: bytes) -> bytes:
    """AES-256-CBC decrypt using cryptography library."""
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    cipher = Cipher(algorithms.AES256(key), modes.CBC(iv))
    decryptor = cipher.decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()
    return pkcs7_unpad(padded)


def pkcs7_pad(data: bytes, block_size: int = 32) -> bytes:
    """PKCS7 padding."""
    pad_len = block_size - (len(data) % block_size)
    return data + bytes([pad_len] * pad_len)


def pkcs7_unpad(data: bytes) -> bytes:
    """Remove PKCS7 padding."""
    if not data:
        return data
    pad_len = data[-1]
    if pad_len == 0 or pad_len > len(data):
        return data
    if data[-pad_len:] != bytes([pad_len] * pad_len):
        return data
    return data[:-pad_len]


def decode_aes_key(encoding_aes_key: str) -> bytes:
    """Decode WeCom EncodingAESKey (43 chars + padding to multiple of 4 → 32 bytes)."""
    import base64
    # Add padding to make length a multiple of 4
    missing = (4 - (len(encoding_aes_key) % 4)) % 4
    key = encoding_aes_key + ("=" * missing)
    return base64.b64decode(key)


def verify_wecom_signature(token: str, timestamp: str, nonce: str, encrypt_msg: str) -> str:
    """Compute WeCom SHA-1 signature."""
    parts = sorted([token, timestamp, nonce, encrypt_msg])
    combined = "".join(parts).encode("utf-8")
    return hashlib.sha1(combined).hexdigest()


def encrypt_wecom_message(plaintext: str, aes_key: bytes, corp_id: str) -> Tuple[bytes, str]:
    """Encrypt a WeCom callback message.

    Returns (ciphertext_bytes, base64_encoded_ciphertext).
    Follows WeCom XML encrypt format:
      16-random-bytes + 4-byte-msg-len + XML-content + corp-id
    """
    import os
    import base64

    random_bytes = os.urandom(16)
    msg_bytes = plaintext.encode("utf-8")
    content = random_bytes + struct.pack(">I", len(msg_bytes)) + msg_bytes + corp_id.encode("utf-8")

    iv = aes_key[:16]
    ciphertext = aes_256_cbc_encrypt(content, aes_key, aes_key[:16])
    return ciphertext, base64.b64encode(ciphertext).decode("utf-8")


def decrypt_wecom_message(base64_ciphertext: str, aes_key: bytes) -> str:
    """Decrypt a WeCom callback message.

    Returns the XML plaintext content (without 16-byte random prefix and corp_id suffix).
    """
    import base64

    ciphertext = base64.b64decode(base64_ciphertext)
    iv = aes_key[:16]
    decrypted = aes_256_cbc_decrypt(ciphertext, aes_key, iv)

    # Parse: 16 random bytes + 4 byte length + XML + corp_id
    msg_len = struct.unpack(">I", decrypted[16:20])[0]
    xml_content = decrypted[20:20 + msg_len].decode("utf-8")
    return xml_content


def build_text_xml(from_user: str, content: str, msg_id: str = None) -> str:
    """Build WeCom XML message body for a text message callback."""
    import time
    if msg_id is None:
        import uuid
        msg_id = str(uuid.uuid4())
    create_time = int(time.time())
    return f"""<xml>
<ToUserName><![CDATA[bot_agentid]]></ToUserName>
<FromUserName><![CDATA[{from_user}]]></FromUserName>
<CreateTime>{create_time}</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[{content}]]></Content>
<MsgId>{msg_id}</MsgId>
<AgentID>test_agent</AgentID>
</xml>"""

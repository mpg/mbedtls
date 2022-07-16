#!/usr/bin/python3
# coding: utf-8

import hashlib

suite = 'pkcs1_v15'

functions = {
        'pkcs1_rsassa_v15_sign': (10, 12),
        'pkcs1_rsassa_v15_verify': (6, 8),
}

def hash_ctx(s):
    if s == 'MBEDTLS_MD_MD5':
        return hashlib.md5()
    if s == 'MBEDTLS_MD_SHA1':
        return hashlib.sha1()
    if s == 'MBEDTLS_MD_SHA224':
        return hashlib.sha224()
    if s == 'MBEDTLS_MD_SHA256':
        return hashlib.sha256()
    if s == 'MBEDTLS_MD_SHA384':
        return hashlib.sha384()
    if s == 'MBEDTLS_MD_SHA512':
        return hashlib.sha512()

def fix(l):
    parts = l.rstrip().split(":")

    fun = parts[0]
    if fun not in functions:
        return l

    (alg_idx, msg_idx) = functions[fun]

    alg_str = parts[alg_idx]
    if alg_str == "MBEDTLS_MD_NONE":
        return l
    h = hash_ctx(alg_str)

    msg_str = parts[msg_idx]
    msg_hex = msg_str[1:-1]
    msg = bytes.fromhex(msg_hex)
    h.update(msg)
    msg_hash = h.hexdigest()
    msg_hash_str = '"' + msg_hash + '"'

    parts[msg_idx] = msg_hash_str
    return ":".join(parts) + '\n'


filename = 'tests/suites/test_suite_' + suite + '.data'
with open(filename) as f:
    lines = f.readlines()

lines = [fix(l) for l in lines]

with open(filename, 'w') as f:
    f.writelines(lines)

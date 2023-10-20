#!/usr/bin/env python3

"""Analyze the test outcomes from a full CI run.

This script can also run on outcomes from a partial run, but the results are
less likely to be useful.
"""

import argparse
import sys
import traceback
import re
import subprocess
import os

import check_test_cases

class Results:
    """Process analysis results."""

    def __init__(self):
        self.error_count = 0
        self.warning_count = 0

    def new_section(self, fmt, *args, **kwargs):
        self._print_line('\n*** ' + fmt + ' ***\n', *args, **kwargs)

    def info(self, fmt, *args, **kwargs):
        self._print_line('Info: ' + fmt, *args, **kwargs)

    def error(self, fmt, *args, **kwargs):
        self.error_count += 1
        self._print_line('Error: ' + fmt, *args, **kwargs)

    def warning(self, fmt, *args, **kwargs):
        self.warning_count += 1
        self._print_line('Warning: ' + fmt, *args, **kwargs)

    @staticmethod
    def _print_line(fmt, *args, **kwargs):
        sys.stderr.write((fmt + '\n').format(*args, **kwargs))

class TestCaseOutcomes:
    """The outcomes of one test case across many configurations."""
    # pylint: disable=too-few-public-methods

    def __init__(self):
        # Collect a list of witnesses of the test case succeeding or failing.
        # Currently we don't do anything with witnesses except count them.
        # The format of a witness is determined by the read_outcome_file
        # function; it's the platform and configuration joined by ';'.
        self.successes = []
        self.failures = []

    def hits(self):
        """Return the number of times a test case has been run.

        This includes passes and failures, but not skips.
        """
        return len(self.successes) + len(self.failures)

def execute_reference_driver_tests(results: Results, ref_component, driver_component, \
                                   outcome_file):
    """Run the tests specified in ref_component and driver_component. Results
    are stored in the output_file and they will be used for the following
    coverage analysis"""
    # If the outcome file already exists, we assume that the user wants to
    # perform the comparison analysis again without repeating the tests.
    if os.path.exists(outcome_file):
        results.info("Outcome file ({}) already exists. Tests will be skipped.", outcome_file)
        return

    shell_command = "tests/scripts/all.sh --outcome-file " + outcome_file + \
                    " " + ref_component + " " + driver_component
    results.info("Running: {}", shell_command)
    ret_val = subprocess.run(shell_command.split(), check=False).returncode

    if ret_val != 0:
        results.error("failed to run reference/driver components")

def analyze_coverage(results, outcomes, allow_list, full_coverage):
    """Check that all available test cases are executed at least once."""
    available = check_test_cases.collect_available_test_cases()
    for key in available:
        hits = outcomes[key].hits() if key in outcomes else 0
        if hits == 0 and key not in allow_list:
            if full_coverage:
                results.error('Test case not executed: {}', key)
            else:
                results.warning('Test case not executed: {}', key)
        elif hits != 0 and key in allow_list:
            # Test Case should be removed from the allow list.
            if full_coverage:
                results.error('Allow listed test case was executed: {}', key)
            else:
                results.warning('Allow listed test case was executed: {}', key)

def analyze_driver_vs_reference(results: Results, outcomes,
                                component_ref, component_driver,
                                ignored_suites, ignored_tests=None):
    """Check that all tests executed in the reference component are also
    executed in the corresponding driver component.
    Skip:
    - full test suites provided in ignored_suites list
    - only some specific test inside a test suite, for which the corresponding
      output string is provided
    """
    seen_reference_passing = False
    for key in outcomes:
        # key is like "test_suite_foo.bar;Description of test case"
        (full_test_suite, test_string) = key.split(';')
        test_suite = full_test_suite.split('.')[0] # retrieve main part of test suite name

        # Immediately skip fully-ignored test suites
        if test_suite in ignored_suites or full_test_suite in ignored_suites:
            continue

        # For ignored test cases inside test suites, just remember and:
        # don't issue an error if they're skipped with drivers,
        # but issue an error if they're not (means we have a bad entry).
        ignored = False
        if full_test_suite in ignored_tests:
            for str_or_re in ignored_tests[full_test_suite]:
                if isinstance(str_or_re, re.Pattern):
                    if str_or_re.fullmatch(test_string):
                        ignored = True
                else:
                    if str_or_re == test_string:
                        ignored = True

        # Search for tests that run in reference component and not in driver component
        driver_test_passed = False
        reference_test_passed = False
        for entry in outcomes[key].successes:
            if component_driver in entry:
                driver_test_passed = True
            if component_ref in entry:
                reference_test_passed = True
                seen_reference_passing = True
        if(reference_test_passed and not driver_test_passed):
            if not ignored:
                results.error("PASS -> SKIP/FAIL: {}", key)
        else:
            if ignored:
                results.error("uselessly ignored: {}", key)

    if not seen_reference_passing:
        results.error("no passing test in reference component: bad outcome file?")

def analyze_outcomes(results: Results, outcomes, args):
    """Run all analyses on the given outcome collection."""
    analyze_coverage(results, outcomes, args['allow_list'],
                     args['full_coverage'])

def read_outcome_file(outcome_file):
    """Parse an outcome file and return an outcome collection.

An outcome collection is a dictionary mapping keys to TestCaseOutcomes objects.
The keys are the test suite name and the test case description, separated
by a semicolon.
"""
    outcomes = {}
    with open(outcome_file, 'r', encoding='utf-8') as input_file:
        for line in input_file:
            (platform, config, suite, case, result, _cause) = line.split(';')
            key = ';'.join([suite, case])
            setup = ';'.join([platform, config])
            if key not in outcomes:
                outcomes[key] = TestCaseOutcomes()
            if result == 'PASS':
                outcomes[key].successes.append(setup)
            elif result == 'FAIL':
                outcomes[key].failures.append(setup)
    return outcomes

def do_analyze_coverage(results: Results, outcome_file, args):
    """Perform coverage analysis."""
    results.new_section("Analyze coverage")
    outcomes = read_outcome_file(outcome_file)
    analyze_outcomes(results, outcomes, args)

def do_analyze_driver_vs_reference(results: Results, outcome_file, args):
    """Perform driver vs reference analyze."""
    results.new_section("Analyze driver {} vs reference {}",
                        args['component_driver'], args['component_ref'])

    execute_reference_driver_tests(results, args['component_ref'], \
                                   args['component_driver'], outcome_file)

    ignored_suites = ['test_suite_' + x for x in args['ignored_suites']]

    outcomes = read_outcome_file(outcome_file)

    analyze_driver_vs_reference(results, outcomes,
                                args['component_ref'], args['component_driver'],
                                ignored_suites, args['ignored_tests'])

# List of tasks with a function that can handle this task and additional arguments if required
KNOWN_TASKS = {
    'analyze_coverage':                 {
        'test_function': do_analyze_coverage,
        'args': {
            'allow_list': [
                # Algorithm not supported yet
                'test_suite_psa_crypto_metadata;Asymmetric signature: pure EdDSA',
                # Algorithm not supported yet
                'test_suite_psa_crypto_metadata;Cipher: XTS',
            ],
            'full_coverage': False,
        }
    },
    # There are 2 options to use analyze_driver_vs_reference_xxx locally:
    # 1. Run tests and then analysis:
    #   - tests/scripts/all.sh --outcome-file "$PWD/out.csv" <component_ref> <component_driver>
    #   - tests/scripts/analyze_outcomes.py out.csv analyze_driver_vs_reference_xxx
    # 2. Let this script run both automatically:
    #   - tests/scripts/analyze_outcomes.py out.csv analyze_driver_vs_reference_xxx
    'analyze_driver_vs_reference_hash': {
        'test_function': do_analyze_driver_vs_reference,
        'args': {
            'component_ref': 'test_psa_crypto_config_reference_hash_use_psa',
            'component_driver': 'test_psa_crypto_config_accel_hash_use_psa',
            'ignored_suites': [
                'shax', 'mdx', # the software implementations that are being excluded
                'md.psa',  # purposefully depends on whether drivers are present
                'psa_crypto_low_hash.generated', # testing the builtins
            ],
            'ignored_tests': {
            }
        }
    },
    'analyze_driver_vs_reference_cipher_aead': {
        'test_function': do_analyze_driver_vs_reference,
        'args': {
            'component_ref': 'test_psa_crypto_config_reference_cipher_aead',
            'component_driver': 'test_psa_crypto_config_accel_cipher_aead',
            # Ignore suites that are being accelerated
            'ignored_suites': [
                'aes.cbc',
                'aes.cfb',
                'aes.ecb',
                'aes.ofb',
                'aes.rest',
                'aes.xts',
                'aria',
                'camellia',
                'ccm',
                'chacha20',
                'chachapoly',
                'cipher.aes',
                'cipher.aria',
                'cipher.camellia',
                'cipher.ccm',
                'cipher.chacha20',
                'cipher.chachapoly',
                'cipher.des',
                'cipher.gcm',
                'cipher.nist_kw',
                'cipher.padding',
                'des',
                'gcm.aes128_de',
                'gcm.aes128_en',
                'gcm.aes192_de',
                'gcm.aes192_en',
                'gcm.aes256_de',
                'gcm.aes256_en',
                'gcm.camellia',
                'gcm.misc',
            ],
            'ignored_tests': {
                # Following tests depends on AES_C/DES_C
                'test_suite_pem': [
                    'PEM read (AES-128-CBC + invalid iv)'
                    'PEM read (DES-CBC + invalid iv)',
                    'PEM read (DES-EDE3-CBC + invalid iv)',
                    'PEM read (malformed PEM AES-128-CBC)',
                    'PEM read (malformed PEM DES-CBC)',
                    'PEM read (malformed PEM DES-EDE3-CBC)',
                    'PEM read (unknown encryption algorithm)',
                    'PEM read (AES-128-CBC + invalid iv)',
                    'PEM read (DES-CBC + invalid iv)',
                ],
                # Following tests depends on AES_C/DES_C
                'test_suite_error': [
                    'Low and high error',
                    'Single low error'
                ],
                # Following tests depends on AES_C/DES_C/GCM_C/CTR
                'test_suite_psa_crypto': [
                    'PSA AEAD encrypt/decrypt: DES-CCM not supported',
                    'PSA AEAD encrypt/decrypt: invalid algorithm (CTR)',
                    'PSA cipher setup: bad algorithm (unknown cipher algorithm)',
                    'PSA cipher setup: incompatible key ChaCha20 for CTR',
                    'PSA cipher setup: invalid key type, CTR',
                    'PSA symmetric decrypt: CCM*-no-tag, input too short (15 bytes)',
                ],
                # Following test depends on AES_C
                'test_suite_version': [
                    'Check for MBEDTLS_AES_C when already present',
                ],
                # Following tests depends on PCKS7
                'test_suite_pkcs12': [
                    'PBE Decrypt, (Invalid padding & PKCS7 padding enabled)',
                    'PBE Decrypt, pad = 7 (OK)',
                    'PBE Decrypt, pad = 8 (Invalid output size)',
                    'PBE Decrypt, pad = 8 (OK)',
                    'PBE Encrypt, pad = 7 (OK)',
                    'PBE Encrypt, pad = 8 (Invalid output size)',
                    'PBE Encrypt, pad = 8 (OK)',
                ],
                # Following tests depends on PCKS7
                'test_suite_pkcs5': [
                    'PBES2 Decrypt (Invalid output size)',
                    'PBES2 Decrypt (Invalid padding & PKCS7 padding enabled)',
                    'PBES2 Decrypt (KDF != PBKDF2)',
                    'PBES2 Decrypt (OK)',
                    'PBES2 Decrypt (OK, PBKDF2 params explicit keylen)',
                    'PBES2 Decrypt (OK, PBKDF2 params explicit prf_alg)',
                    'PBES2 Decrypt (bad KDF AlgId: not a sequence)',
                    'PBES2 Decrypt (bad KDF AlgId: overlong)',
                    'PBES2 Decrypt (bad PBKDF2 params explicit keylen: overlong)',
                    'PBES2 Decrypt (bad PBKDF2 params iter: not an int)',
                    'PBES2 Decrypt (bad PBKDF2 params iter: overlong)',
                    'PBES2 Decrypt (bad PBKDF2 params salt: not an octet string)',
                    'PBES2 Decrypt (bad PBKDF2 params salt: overlong)',
                    'PBES2 Decrypt (bad PBKDF2 params: not a sequence)',
                    'PBES2 Decrypt (bad PBKDF2 params: overlong)',
                    'PBES2 Decrypt (bad enc_scheme_alg params: len != iv_len)',
                    'PBES2 Decrypt (bad enc_scheme_alg params: not an octet string)',
                    'PBES2 Decrypt (bad enc_scheme_alg params: overlong)',
                    'PBES2 Decrypt (bad enc_scheme_alg: not a sequence)',
                    'PBES2 Decrypt (bad enc_scheme_alg: overlong)',
                    'PBES2 Decrypt (bad enc_scheme_alg: unknown oid)',
                    'PBES2 Decrypt (bad iter value)',
                    'PBES2 Decrypt (bad params tag)',
                    'PBES2 Decrypt (bad password)',
                    'PBES2 Decrypt (bad, PBKDF2 params explicit prf_alg != HMAC-SHA*)',
                    'PBES2 Decrypt (bad, PBKDF2 params explicit prf_alg not a sequence)',
                    'PBES2 Decrypt (bad, PBKDF2 params explicit prf_alg overlong)',
                    'PBES2 Decrypt (bad, PBKDF2 params extra data)',
                    'PBES2 Encrypt, pad=6 (OK)',
                    'PBES2 Encrypt, pad=8 (Invalid output size)',
                    'PBES2 Encrypt, pad=8 (OK)',
                ],
                # Following tests depends on DES
                # pylint: disable=line-too-long
                'test_suite_pkparse': [
                    'Key ASN1 (Encrypted key PKCS12, trailing garbage data)',
                    'Key ASN1 (Encrypted key PKCS5, trailing garbage data)',
                    'Parse RSA Key #20 (PKCS#8 encrypted SHA1-3DES)',
                    'Parse RSA Key #20.1 (PKCS#8 encrypted SHA1-3DES, wrong PW)',
                    'Parse RSA Key #20.2 (PKCS#8 encrypted SHA1-3DES, no PW)',
                    'Parse RSA Key #21 (PKCS#8 encrypted SHA1-3DES, 2048-bit)',
                    'Parse RSA Key #21.1 (PKCS#8 encrypted SHA1-3DES, 2048-bit, wrong PW)',
                    'Parse RSA Key #21.2 (PKCS#8 encrypted SHA1-3DES, 2048-bit, no PW)',
                    'Parse RSA Key #22 (PKCS#8 encrypted SHA1-3DES, 4096-bit)',
                    'Parse RSA Key #22.1 (PKCS#8 encrypted SHA1-3DES, 4096-bit, wrong PW)',
                    'Parse RSA Key #22.2 (PKCS#8 encrypted SHA1-3DES, 4096-bit, no PW)',
                    'Parse RSA Key #23 (PKCS#8 encrypted SHA1-3DES DER)',
                    'Parse RSA Key #24 (PKCS#8 encrypted SHA1-3DES DER, 2048-bit)',
                    'Parse RSA Key #25 (PKCS#8 encrypted SHA1-3DES DER, 4096-bit)',
                    'Parse RSA Key #26 (PKCS#8 encrypted SHA1-2DES)',
                    'Parse RSA Key #26.1 (PKCS#8 encrypted SHA1-2DES, wrong PW)',
                    'Parse RSA Key #26.2 (PKCS#8 encrypted SHA1-2DES, no PW)',
                    'Parse RSA Key #27 (PKCS#8 encrypted SHA1-2DES, 2048-bit)',
                    'Parse RSA Key #27.1 (PKCS#8 encrypted SHA1-2DES, 2048-bit, wrong PW)',
                    'Parse RSA Key #27.2 (PKCS#8 encrypted SHA1-2DES, 2048-bit no PW)',
                    'Parse RSA Key #28 (PKCS#8 encrypted SHA1-2DES, 4096-bit)',
                    'Parse RSA Key #28.1 (PKCS#8 encrypted SHA1-2DES, 4096-bit, wrong PW)',
                    'Parse RSA Key #28.2 (PKCS#8 encrypted SHA1-2DES, 4096-bit, no PW)',
                    'Parse RSA Key #29 (PKCS#8 encrypted SHA1-2DES DER)',
                    'Parse RSA Key #30 (PKCS#8 encrypted SHA1-2DES DER, 2048-bit)',
                    'Parse RSA Key #31 (PKCS#8 encrypted SHA1-2DES DER, 4096-bit)',
                    'Parse RSA Key #38 (PKCS#8 encrypted v2 PBKDF2 3DES)',
                    'Parse RSA Key #38.1 (PKCS#8 encrypted v2 PBKDF2 3DES, wrong PW)',
                    'Parse RSA Key #38.2 (PKCS#8 encrypted v2 PBKDF2 3DES, no PW)',
                    'Parse RSA Key #39 (PKCS#8 encrypted v2 PBKDF2 3DES, 2048-bit)',
                    'Parse RSA Key #39.1 (PKCS#8 encrypted v2 PBKDF2 3DES, 2048-bit, wrong PW)',
                    'Parse RSA Key #39.2 (PKCS#8 encrypted v2 PBKDF2 3DES, 2048-bit, no PW)',
                    'Parse RSA Key #40 (PKCS#8 encrypted v2 PBKDF2 3DES, 4096-bit)',
                    'Parse RSA Key #40.1 (PKCS#8 encrypted v2 PBKDF2 3DES, 4096-bit, wrong PW)',
                    'Parse RSA Key #40.2 (PKCS#8 encrypted v2 PBKDF2 3DES, 4096-bit, no PW)',
                    'Parse RSA Key #41 (PKCS#8 encrypted v2 PBKDF2 3DES DER)',
                    'Parse RSA Key #41.1 (PKCS#8 encrypted v2 PBKDF2 3DES DER, wrong PW)',
                    'Parse RSA Key #41.2 (PKCS#8 encrypted v2 PBKDF2 3DES DER, no PW)',
                    'Parse RSA Key #42 (PKCS#8 encrypted v2 PBKDF2 3DES DER, 2048-bit)',
                    'Parse RSA Key #42.1 (PKCS#8 encrypted v2 PBKDF2 3DES DER, 2048-bit, wrong PW)',
                    'Parse RSA Key #42.2 (PKCS#8 encrypted v2 PBKDF2 3DES DER, 2048-bit, no PW)',
                    'Parse RSA Key #43 (PKCS#8 encrypted v2 PBKDF2 3DES DER, 4096-bit)',
                    'Parse RSA Key #43.1 (PKCS#8 encrypted v2 PBKDF2 3DES DER, 4096-bit, wrong PW)',
                    'Parse RSA Key #43.2 (PKCS#8 encrypted v2 PBKDF2 3DES DER, 4096-bit, no PW)',
                    'Parse RSA Key #44 (PKCS#8 encrypted v2 PBKDF2 DES)',
                    'Parse RSA Key #44.1 (PKCS#8 encrypted v2 PBKDF2 DES, wrong PW)',
                    'Parse RSA Key #44.2 (PKCS#8 encrypted v2 PBKDF2 DES, no PW)',
                    'Parse RSA Key #45 (PKCS#8 encrypted v2 PBKDF2 DES, 2048-bit)',
                    'Parse RSA Key #45.1 (PKCS#8 encrypted v2 PBKDF2 DES, 2048-bit, wrong PW)',
                    'Parse RSA Key #45.2 (PKCS#8 encrypted v2 PBKDF2 DES, 2048-bit, no PW)',
                    'Parse RSA Key #46 (PKCS#8 encrypted v2 PBKDF2 DES, 4096-bit)',
                    'Parse RSA Key #46.1 (PKCS#8 encrypted v2 PBKDF2 DES, 4096-bit, wrong PW)',
                    'Parse RSA Key #46.2 (PKCS#8 encrypted v2 PBKDF2 DES, 4096-bit, no PW)',
                    'Parse RSA Key #47 (PKCS#8 encrypted v2 PBKDF2 DES DER)',
                    'Parse RSA Key #47.1 (PKCS#8 encrypted v2 PBKDF2 DES DER, wrong PW)',
                    'Parse RSA Key #47.2 (PKCS#8 encrypted v2 PBKDF2 DES DER, no PW)',
                    'Parse RSA Key #48 (PKCS#8 encrypted v2 PBKDF2 DES DER, 2048-bit)',
                    'Parse RSA Key #48.1 (PKCS#8 encrypted v2 PBKDF2 DES DER, 2048-bit, wrong PW)',
                    'Parse RSA Key #48.2 (PKCS#8 encrypted v2 PBKDF2 DES DER, 2048-bit, no PW)',
                    'Parse RSA Key #49 (PKCS#8 encrypted v2 PBKDF2 DES DER, 4096-bit)',
                    'Parse RSA Key #49.1 (PKCS#8 encrypted v2 PBKDF2 DES DER, 4096-bit, wrong PW)',
                    'Parse RSA Key #49.2 (PKCS#8 encrypted v2 PBKDF2 DES DER, 4096-bit, no PW)',
                    'Parse RSA Key #50 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA224)',
                    'Parse RSA Key #50.1 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA224, wrong PW)',
                    'Parse RSA Key #50.2 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA224, no PW)',
                    'Parse RSA Key #51 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA224, 2048-bit)',
                    'Parse RSA Key #51.1 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA224, 2048-bit, wrong PW)',
                    'Parse RSA Key #51.2 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA224, 2048-bit, no PW)',
                    'Parse RSA Key #52 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA224, 4096-bit)',
                    'Parse RSA Key #52.1 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA224, 4096-bit, wrong PW)',
                    'Parse RSA Key #52.2 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA224, 4096-bit, no PW)',
                    'Parse RSA Key #53 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA224 DER)',
                    'Parse RSA Key #53.1 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA224 DER, wrong PW)',
                    'Parse RSA Key #53.2 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA224 DER, no PW)',
                    'Parse RSA Key #54 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA224 DER, 2048-bit)',
                    'Parse RSA Key #54.1 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA224 DER, 2048-bit, wrong PW)',
                    'Parse RSA Key #54.2 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA224 DER, 2048-bit, no PW)',
                    'Parse RSA Key #55 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA224 DER, 4096-bit)',
                    'Parse RSA Key #55.1 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA224 DER, 4096-bit, wrong PW)',
                    'Parse RSA Key #55.2 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA224 DER, 4096-bit, no PW)',
                    'Parse RSA Key #56 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA224)',
                    'Parse RSA Key #56.1 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA224, wrong PW)',
                    'Parse RSA Key #56.2 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA224, no PW)',
                    'Parse RSA Key #57 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA224, 2048-bit)',
                    'Parse RSA Key #57.1 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA224, 2048-bit, wrong PW)',
                    'Parse RSA Key #57.2 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA224, 2048-bit, no PW)',
                    'Parse RSA Key #58 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA224, 4096-bit)',
                    'Parse RSA Key #58.1 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA224, 4096-bit, wrong PW)',
                    'Parse RSA Key #58.2 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA224, 4096-bit, no PW)',
                    'Parse RSA Key #59 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA224 DER)',
                    'Parse RSA Key #59.1 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA224 DER, wrong PW)',
                    'Parse RSA Key #59.2 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA224 DER, no PW)',
                    'Parse RSA Key #60 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA224 DER, 2048-bit)',
                    'Parse RSA Key #60.1 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA224 DER, 2048-bit, wrong PW)',
                    'Parse RSA Key #60.2 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA224 DER, 2048-bit, no PW)',
                    'Parse RSA Key #61 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA224 DER, 4096-bit)',
                    'Parse RSA Key #61.1 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA224 DER, 4096-bit, wrong PW)',
                    'Parse RSA Key #61.2 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA224 DER, 4096-bit, no PW)',
                    'Parse RSA Key #62 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA256)',
                    'Parse RSA Key #62.1 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA256, wrong PW)',
                    'Parse RSA Key #62.2 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA256, no PW)',
                    'Parse RSA Key #63 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA256, 2048-bit)',
                    'Parse RSA Key #63.1 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA256, 2048-bit, wrong PW)',
                    'Parse RSA Key #63.2 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA256, 2048-bit, no PW)',
                    'Parse RSA Key #64 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA256, 4096-bit)',
                    'Parse RSA Key #64.1 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA256, 4096-bit, wrong PW)',
                    'Parse RSA Key #64.2 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA256, 4096-bit, no PW)',
                    'Parse RSA Key #65 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA256 DER)',
                    'Parse RSA Key #65.1 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA256 DER, wrong PW)',
                    'Parse RSA Key #65.2 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA256 DER, no PW)',
                    'Parse RSA Key #66 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA256 DER, 2048-bit)',
                    'Parse RSA Key #66.1 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA256 DER, 2048-bit, wrong PW)',
                    'Parse RSA Key #66.2 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA256 DER, 2048-bit, no PW)',
                    'Parse RSA Key #67 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA256 DER, 4096-bit)',
                    'Parse RSA Key #68.1 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA256 DER, 4096-bit, wrong PW)',
                    'Parse RSA Key #68.2 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA256 DER, 4096-bit, no PW)',
                    'Parse RSA Key #69 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA256)',
                    'Parse RSA Key #69.1 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA256, wrong PW)',
                    'Parse RSA Key #69.2 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA256, no PW)',
                    'Parse RSA Key #70 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA256, 2048-bit)',
                    'Parse RSA Key #70.1 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA256, 2048-bit, wrong PW)',
                    'Parse RSA Key #70.2 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA256, 2048-bit, no PW)',
                    'Parse RSA Key #71 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA256, 4096-bit)',
                    'Parse RSA Key #71.1 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA256, 4096-bit, wrong PW)',
                    'Parse RSA Key #71.2 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA256, 4096-bit, no PW)',
                    'Parse RSA Key #72 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA256 DER)',
                    'Parse RSA Key #72.1 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA256 DER, wrong PW)',
                    'Parse RSA Key #72.2 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA256 DER, no PW)',
                    'Parse RSA Key #73 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA256 DER, 2048-bit)',
                    'Parse RSA Key #73.1 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA256 DER, 2048-bit, wrong PW)',
                    'Parse RSA Key #73.2 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA256 DER, 2048-bit, no PW)',
                    'Parse RSA Key #74 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA256 DER, 4096-bit)',
                    'Parse RSA Key #74.1 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA256 DER, 4096-bit, wrong PW)',
                    'Parse RSA Key #74.2 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA256 DER, 4096-bit, no PW)',
                    'Parse RSA Key #75 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA384)',
                    'Parse RSA Key #75.1 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA384, wrong PW)',
                    'Parse RSA Key #75.2 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA384, no PW)',
                    'Parse RSA Key #76 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA384, 2048-bit)',
                    'Parse RSA Key #76.1 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA384, 2048-bit, wrong PW)',
                    'Parse RSA Key #76.2 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA384, 2048-bit, no PW)',
                    'Parse RSA Key #77 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA384, 4096-bit)',
                    'Parse RSA Key #77.1 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA384, 4096-bit, wrong PW)',
                    'Parse RSA Key #77.2 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA384, 4096-bit, no PW)',
                    'Parse RSA Key #78 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA384 DER)',
                    'Parse RSA Key #78.1 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA384 DER, wrong PW)',
                    'Parse RSA Key #78.2 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA384 DER, no PW)',
                    'Parse RSA Key #79 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA384 DER, 2048-bit)',
                    'Parse RSA Key #79.1 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA384 DER, 2048-bit, wrong PW)',
                    'Parse RSA Key #79.2 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA384 DER, 2048-bit, no PW)',
                    'Parse RSA Key #80 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA384 DER, 4096-bit)',
                    'Parse RSA Key #80.1 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA384 DER, 4096-bit, wrong PW)',
                    'Parse RSA Key #80.2 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA384 DER, 4096-bit, no PW)',
                    'Parse RSA Key #81 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA384)',
                    'Parse RSA Key #81.1 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA384, wrong PW)',
                    'Parse RSA Key #81.2 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA384, no PW)',
                    'Parse RSA Key #82 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA384, 2048-bit)',
                    'Parse RSA Key #82.1 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA384, 2048-bit, wrong PW)',
                    'Parse RSA Key #82.2 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA384, 2048-bit, no PW)',
                    'Parse RSA Key #83 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA384, 4096-bit)',
                    'Parse RSA Key #83.1 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA384, 4096-bit, wrong PW)',
                    'Parse RSA Key #83.2 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA384, 4096-bit, no PW)',
                    'Parse RSA Key #84 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA384 DER)',
                    'Parse RSA Key #84.1 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA384 DER, wrong PW)',
                    'Parse RSA Key #85.2 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA384 DER, no PW)',
                    'Parse RSA Key #86 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA384 DER, 2048-bit)',
                    'Parse RSA Key #86.1 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA384 DER, 2048-bit, wrong PW)',
                    'Parse RSA Key #86.2 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA384 DER, 2048-bit, no PW)',
                    'Parse RSA Key #87 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA384 DER, 4096-bit)',
                    'Parse RSA Key #87.1 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA384 DER, 4096-bit, wrong PW)',
                    'Parse RSA Key #87.2 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA384 DER, 4096-bit, no PW)',
                    'Parse RSA Key #88 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA512)',
                    'Parse RSA Key #88.1 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA512, wrong PW)',
                    'Parse RSA Key #88.2 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA512, no PW)',
                    'Parse RSA Key #89 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA512, 2048-bit)',
                    'Parse RSA Key #89.1 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA512, 2048-bit, wrong PW)',
                    'Parse RSA Key #89.2 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA512, 2048-bit, no PW)',
                    'Parse RSA Key #90 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA512, 4096-bit)',
                    'Parse RSA Key #90.1 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA512, 4096-bit, wrong PW)',
                    'Parse RSA Key #90.2 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA512, 4096-bit, no PW)',
                    'Parse RSA Key #91 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA512 DER)',
                    'Parse RSA Key #91.1 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA512 DER, wrong PW)',
                    'Parse RSA Key #91.2 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA512 DER, no PW)',
                    'Parse RSA Key #92 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA512 DER, 2048-bit)',
                    'Parse RSA Key #92.1 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA512 DER, 2048-bit, wrong PW)',
                    'Parse RSA Key #92.2 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA512 DER, 2048-bit, no PW)',
                    'Parse RSA Key #93 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA512 DER, 4096-bit)',
                    'Parse RSA Key #93.1 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA512 DER, 4096-bit, wrong PW)',
                    'Parse RSA Key #93.2 (PKCS#8 encrypted v2 PBKDF2 3DES hmacWithSHA512 DER, 4096-bit, no PW)',
                    'Parse RSA Key #94 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA512)',
                    'Parse RSA Key #94.1 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA512, wrong PW)',
                    'Parse RSA Key #94.2 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA512, no PW)',
                    'Parse RSA Key #95 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA512, 2048-bit)',
                    'Parse RSA Key #95.1 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA512, 2048-bit, wrong PW)',
                    'Parse RSA Key #95.2 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA512, 2048-bit, no PW)',
                    'Parse RSA Key #96 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA512, 4096-bit)',
                    'Parse RSA Key #96.1 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA512, 4096-bit, wrong PW)',
                    'Parse RSA Key #96.2 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA512, 4096-bit, no PW)',
                    'Parse RSA Key #97 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA512 DER)',
                    'Parse RSA Key #97.1 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA512 DER, wrong PW)',
                    'Parse RSA Key #97.2 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA512 DER, no PW)',
                    'Parse RSA Key #98 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA512 DER, 2048-bit)',
                    'Parse RSA Key #98.1 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA512 DER, 2048-bit, wrong PW)',
                    'Parse RSA Key #98.2 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA512 DER, 2048-bit, no PW)',
                    'Parse RSA Key #99 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA512 DER, 4096-bit)',
                    'Parse RSA Key #99.1 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA512 DER, 4096-bit, wrong PW)',
                    'Parse RSA Key #99.2 (PKCS#8 encrypted v2 PBKDF2 DES hmacWithSHA512 DER, 4096-bit, no PW)',
                ],
            }
        }
    },
    'analyze_driver_vs_reference_ecp_light_only': {
        'test_function': do_analyze_driver_vs_reference,
        'args': {
            'component_ref': 'test_psa_crypto_config_reference_ecc_ecp_light_only',
            'component_driver': 'test_psa_crypto_config_accel_ecc_ecp_light_only',
            'ignored_suites': [
                # Modules replaced by drivers
                'ecdsa', 'ecdh', 'ecjpake',
            ],
            'ignored_tests': {
                # This test wants a legacy function that takes f_rng, p_rng
                # arguments, and uses legacy ECDSA for that. The test is
                # really about the wrapper around the PSA RNG, not ECDSA.
                'test_suite_random': [
                    'PSA classic wrapper: ECDSA signature (SECP256R1)',
                ],
                # In the accelerated test ECP_C is not set (only ECP_LIGHT is)
                # so we must ignore disparities in the tests for which ECP_C
                # is required.
                'test_suite_ecp': [
                    re.compile('ECP check public-private .*'),
                    re.compile('ECP gen keypair .*'),
                    re.compile('ECP point muladd .*'),
                    re.compile('ECP point multiplication .*'),
                    re.compile('ECP test vectors .*'),
                ],
                # This deprecated function is only present when ECP_C is On.
                'test_suite_ssl': [
                    'Test configuration of groups for DHE through mbedtls_ssl_conf_curves()',
                ],
            }
        }
    },
    'analyze_driver_vs_reference_no_ecp_at_all': {
        'test_function': do_analyze_driver_vs_reference,
        'args': {
            'component_ref': 'test_psa_crypto_config_reference_ecc_no_ecp_at_all',
            'component_driver': 'test_psa_crypto_config_accel_ecc_no_ecp_at_all',
            'ignored_suites': [
                # Modules replaced by drivers
                'ecp', 'ecdsa', 'ecdh', 'ecjpake',
            ],
            'ignored_tests': {
                # See ecp_light_only
                'test_suite_random': [
                    'PSA classic wrapper: ECDSA signature (SECP256R1)',
                ],
                'test_suite_pkparse': [
                    # When PK_PARSE_C and ECP_C are defined then PK_PARSE_EC_COMPRESSED
                    # is automatically enabled in build_info.h (backward compatibility)
                    # even if it is disabled in config_psa_crypto_no_ecp_at_all(). As a
                    # consequence compressed points are supported in the reference
                    # component but not in the accelerated one, so they should be skipped
                    # while checking driver's coverage.
                    re.compile('Parse EC Key .*compressed\)'),
                    re.compile('Parse Public EC Key .*compressed\)'),
                ],
                # See ecp_light_only
                'test_suite_ssl': [
                    'Test configuration of groups for DHE through mbedtls_ssl_conf_curves()',
                ],
            }
        }
    },
    'analyze_driver_vs_reference_ecc_no_bignum': {
        'test_function': do_analyze_driver_vs_reference,
        'args': {
            'component_ref': 'test_psa_crypto_config_reference_ecc_no_bignum',
            'component_driver': 'test_psa_crypto_config_accel_ecc_no_bignum',
            'ignored_suites': [
                # Modules replaced by drivers
                'ecp', 'ecdsa', 'ecdh', 'ecjpake',
                'bignum_core', 'bignum_random', 'bignum_mod', 'bignum_mod_raw',
                'bignum.generated', 'bignum.misc',
            ],
            'ignored_tests': {
                # See ecp_light_only
                'test_suite_random': [
                    'PSA classic wrapper: ECDSA signature (SECP256R1)',
                ],
                # See no_ecp_at_all
                'test_suite_pkparse': [
                    re.compile('Parse EC Key .*compressed\)'),
                    re.compile('Parse Public EC Key .*compressed\)'),
                ],
                'test_suite_asn1parse': [
                    'INTEGER too large for mpi',
                ],
                'test_suite_asn1write': [
                    re.compile('ASN.1 Write mpi.*'),
                ],
                'test_suite_debug': [
                    re.compile('Debug print mbedtls_mpi.*'),
                ],
                # See ecp_light_only
                'test_suite_ssl': [
                    'Test configuration of groups for DHE through mbedtls_ssl_conf_curves()',
                ],
            }
        }
    },
    'analyze_driver_vs_reference_ecc_ffdh_no_bignum': {
        'test_function': do_analyze_driver_vs_reference,
        'args': {
            'component_ref': 'test_psa_crypto_config_reference_ecc_ffdh_no_bignum',
            'component_driver': 'test_psa_crypto_config_accel_ecc_ffdh_no_bignum',
            'ignored_suites': [
                # Modules replaced by drivers
                'ecp', 'ecdsa', 'ecdh', 'ecjpake', 'dhm',
                'bignum_core', 'bignum_random', 'bignum_mod', 'bignum_mod_raw',
                'bignum.generated', 'bignum.misc',
            ],
            'ignored_tests': {
                # See ecp_light_only
                'test_suite_random': [
                    'PSA classic wrapper: ECDSA signature (SECP256R1)',
                ],
                # See no_ecp_at_all
                'test_suite_pkparse': [
                    re.compile('Parse EC Key .*compressed\)'),
                    re.compile('Parse Public EC Key .*compressed\)'),
                ],
                'test_suite_asn1parse': [
                    'INTEGER too large for mpi',
                ],
                'test_suite_asn1write': [
                    re.compile('ASN.1 Write mpi.*'),
                ],
                'test_suite_debug': [
                    re.compile('Debug print mbedtls_mpi.*'),
                ],
                # See ecp_light_only
                'test_suite_ssl': [
                    'Test configuration of groups for DHE through mbedtls_ssl_conf_curves()',
                ],
            }
        }
    },
    'analyze_driver_vs_reference_ffdh_alg': {
        'test_function': do_analyze_driver_vs_reference,
        'args': {
            'component_ref': 'test_psa_crypto_config_reference_ffdh',
            'component_driver': 'test_psa_crypto_config_accel_ffdh',
            'ignored_suites': ['dhm'],
            'ignored_tests': {}
        }
    },
    'analyze_driver_vs_reference_tfm_config': {
        'test_function':  do_analyze_driver_vs_reference,
        'args': {
            'component_ref': 'test_tfm_config',
            'component_driver': 'test_tfm_config_p256m_driver_accel_ec',
            'ignored_suites': [
                # Modules replaced by drivers
                'ecp', 'ecdsa', 'ecdh', 'ecjpake',
                'bignum_core', 'bignum_random', 'bignum_mod', 'bignum_mod_raw',
                'bignum.generated', 'bignum.misc',
            ],
            'ignored_tests': {
                # See ecp_light_only
                'test_suite_random': [
                    'PSA classic wrapper: ECDSA signature (SECP256R1)',
                ],
                'test_suite_asn1parse': [
                    'INTEGER too large for mpi',
                ],
                'test_suite_asn1write': [
                    re.compile('ASN.1 Write mpi.*'),
                ],
            }
        }
    }
}

def main():
    main_results = Results()

    try:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument('outcomes', metavar='OUTCOMES.CSV',
                            help='Outcome file to analyze')
        parser.add_argument('specified_tasks', default='all', nargs='?',
                            help='Analysis to be done. By default, run all tasks. '
                                 'With one or more TASK, run only those. '
                                 'TASK can be the name of a single task or '
                                 'comma/space-separated list of tasks. ')
        parser.add_argument('--list', action='store_true',
                            help='List all available tasks and exit.')
        parser.add_argument('--require-full-coverage', action='store_true',
                            dest='full_coverage', help="Require all available "
                            "test cases to be executed and issue an error "
                            "otherwise. This flag is ignored if 'task' is "
                            "neither 'all' nor 'analyze_coverage'")
        options = parser.parse_args()

        if options.list:
            for task in KNOWN_TASKS:
                print(task)
            sys.exit(0)

        if options.specified_tasks == 'all':
            tasks_list = KNOWN_TASKS.keys()
        else:
            tasks_list = re.split(r'[, ]+', options.specified_tasks)
            for task in tasks_list:
                if task not in KNOWN_TASKS:
                    sys.stderr.write('invalid task: {}\n'.format(task))
                    sys.exit(2)

        KNOWN_TASKS['analyze_coverage']['args']['full_coverage'] = options.full_coverage

        for task in tasks_list:
            test_function = KNOWN_TASKS[task]['test_function']
            test_args = KNOWN_TASKS[task]['args']
            test_function(main_results, options.outcomes, test_args)

        main_results.info("Overall results: {} warnings and {} errors",
                          main_results.warning_count, main_results.error_count)

        sys.exit(0 if (main_results.error_count == 0) else 1)

    except Exception: # pylint: disable=broad-except
        # Print the backtrace and exit explicitly with our chosen status.
        traceback.print_exc()
        sys.exit(120)

if __name__ == '__main__':
    main()

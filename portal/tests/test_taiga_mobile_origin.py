from __future__ import annotations

import os
import unittest
from unittest import mock

from portal.core.security import same_origin


class TaigaMobileOriginTests(unittest.TestCase):
    def test_mobile_chrome_null_origin_is_allowed_only_with_same_site_fetch_metadata(self):
        headers={
            "Origin":"null",
            "Sec-Fetch-Site":"same-origin",
            "Sec-Fetch-Mode":"navigate",
            "Host":"cloudiff.duckdns.org",
        }
        with mock.patch.dict(os.environ,{"CLOUDIF_PUBLIC_HOST":"cloudiff.duckdns.org"}):
            self.assertTrue(same_origin(headers,"cloudiff.duckdns.org"))
            self.assertFalse(same_origin({**headers,"Sec-Fetch-Site":"cross-site"},"cloudiff.duckdns.org"))
            self.assertFalse(same_origin({**headers,"Sec-Fetch-Mode":"websocket"},"cloudiff.duckdns.org"))
            self.assertFalse(same_origin(headers,"evil.example"))

    def test_https_cloudiff_origin_remains_allowed_and_foreign_origin_rejected(self):
        with mock.patch.dict(os.environ,{"CLOUDIF_PUBLIC_HOST":"cloudiff.duckdns.org"}):
            self.assertTrue(same_origin({"Origin":"https://cloudiff.duckdns.org"},"cloudiff.duckdns.org"))
            self.assertTrue(same_origin({"Origin":"https://foo.cloudiff.duckdns.org"},"cloudiff.duckdns.org"))
            self.assertFalse(same_origin({"Origin":"https://evil.example"},"cloudiff.duckdns.org"))

    def test_null_origin_without_fetch_metadata_is_rejected(self):
        with mock.patch.dict(os.environ,{"CLOUDIF_PUBLIC_HOST":"cloudiff.duckdns.org"}):
            self.assertFalse(same_origin({"Origin":"null"},"cloudiff.duckdns.org"))

if __name__ == "__main__":
    unittest.main()

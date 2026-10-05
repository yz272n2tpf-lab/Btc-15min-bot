#!/usr/bin/env python3
"""Isolated shadow child entry: exact frozen MAIN runtime, no production receipt."""
from btc15_v2_product.release import verify_files
verify_files("main")
from btc15_v2_product.runtime import native_main
native_main()

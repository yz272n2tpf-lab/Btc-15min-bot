"""Reviewed coordinated product launcher. Default is offline assembly only."""
import argparse
import os
from pathlib import Path

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--lane',choices=['main','v81'],required=True)
    p.add_argument('--run-reviewed-production',action='store_true')
    p.add_argument('--directory',type=Path,default=Path('/tmp/btc15_v2_product_r1'))
    a=p.parse_args()
    from btc15_v2_product.release import verify_files,verify_environment,ROOT
    verify_files(a.lane)
    if not a.run_reviewed_production:
        if a.lane=='main':
            from btc15_v2_product.installer import assemble
            print(assemble(a.directory)/'manifest.json')
        else:print('V81 offline source verification complete. No runtime started.')
        return 0
    verify_environment(a.lane)
    if a.lane=='v81':
        from btc15_v2_product.runtime import v81_main
        return v81_main(ROOT)
    if os.getenv('BTC15_ENABLE_INFORMATION_EXPORT')!='1':raise ValueError('INFORMATION_EXPORT_OPT_IN_REQUIRED')
    if Path.cwd().resolve()!=ROOT:raise ValueError('REPOSITORY_WORKING_DIRECTORY_REQUIRED')
    import fcntl
    from btc15_information_install_v1 import supervise
    from btc15_v2_product.installer import assemble
    with open('/tmp/btc15-two-clock.lock','a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        return supervise(assemble(a.directory))

if __name__=='__main__':raise SystemExit(main())

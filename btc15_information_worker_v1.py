"""Resource envelope applies ONLY to the optional information child."""
import os
import resource


def configure():
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
        os.environ[name] = '1'
    os.nice(10)
    # At most one logical CPU; lower scheduling priority than original owners.
    available = os.sched_getaffinity(0)
    os.sched_setaffinity(0, {max(available)})
    resource.setrlimit(resource.RLIMIT_AS, (2*1024**3, 2*1024**3))
    resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))


if __name__ == '__main__':
    configure()
    from btc15_information_service_v1 import main
    main()

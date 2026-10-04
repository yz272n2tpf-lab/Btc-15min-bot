"""Child entry point selected only by the reviewed product launcher."""
if __name__=='__main__':
    from btc15_v2_product.release import verify_environment
    verify_environment('main')
    from btc15_v2_product.runtime import native_main
    native_main()

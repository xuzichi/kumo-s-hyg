__versions__ = "0.0.1"


# 如果参数是 --version 或 -v，打印版本号
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] in ("--version", "-v"):
        print(__versions__)
        sys.exit(0)
        
        
        
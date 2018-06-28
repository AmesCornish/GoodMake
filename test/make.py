#! /usr/local/bin/goodmake /usr/bin/python3 -

#? tgt/*
    import subprocess
    import sys

#? tgt/sorted.txt
    inputFile = 'src/input.txt'
    subprocess.run([sys.argv[2], inputFile])

    with open(inputFile) as input:
        lines = input.readlines()
        lines.sort()
        with open(sys.argv[1], 'w') as output:
            output.writelines(lines)

#! !sayhi
    print("Hello, World")

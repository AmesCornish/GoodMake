#! sed

s/[-0-9]\{10\} [0-9:.]\{15\}/XXXX-XX-XX XX:XX:XX.XXXXXX/g
s/GoodMake version [-a-zA-Z0-9.]\{5,\}/GoodMake version X.X.X/
s/Sleep for [0-9.]\{10,\}/Sleep for X.XXXXXXXXXXXXXXXXX/

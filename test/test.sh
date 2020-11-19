#!/bin/bash
# Basic regression test script for ss2em.py

ss2em=../src/ss2em.py

echo "start test"
rm -f -r out
count=0

runtest() {
    $ss2em $*
    echo "result:"
    diff -qrN out/test2/ results/test2/
    if [ $? -ne 0 ]; then
        echo "TEST FAILING";
        count=$((count+1))
    else
        echo "TEST pass";
    fi
}

echo
echo "==== Test 1:"
$ss2em -w internal-template.txt 
rm internal-template.txt 

echo
echo "==== Test 2:"
    runtest "-p public -o out/test2 --type f --if ALPHA,Gamma,beta  -u Test-template.txt" 

echo
echo "==== Test 3:"
runtest "-p public -o out/test3 --type c --if ALPHA,Gamma  -u Test-template.txt"

echo
echo "==== Test 4:"
runtest "-p public -o out/test4 --type m --if ALPHA,Gamma,beta  -u Test-template.txt"

echo
echo "==== Test 5:"
runtest "-p public -o out/test5 --type m -i all.h --if ALPHA,beta  -u Test-template.txt"

if [[ "$count" -gt 0 ]]; then
    echo "FAILED"
else
    echo "PASS"
    rm -f -r out
fi
echo
echo "test completed"

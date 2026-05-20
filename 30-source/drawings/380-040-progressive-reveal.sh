#!/usr/bin/env bash

#tag draw each line with sleep interval

echo ""
echo "Progressively executes lines from a dsl file and"
echo "draws the SVG after each additional line."
echo " -- interval is hard-coded"
echo ""

tmpfile=zz.dsl
wclines=$(wc -l "$1")
nlines=$(echo "$wclines" | cut -d ' ' -f1)

for ((i = 1; i <= nlines; i++));  do
    sed -n "1,${i}p"  "$1" > $tmpfile
    bash /srv/380-svg/30-source/bin/380-010.sh $tmpfile
    sleep 1
done

#!/usr/bin/env bash
#tag Search dsl files for include files that don't exist

rm bad-includes.tmp

for f in *dsl; do
    grep -RhoP 'include\s+\K\S+' "$f" >> bad-includes.tmp
done

if [ -s bad-includes.tmp ]; then 
    echo ""; echo "[dark_orange]DSL include files not found:[/]" | rich -p -
    sort -u bad-includes.tmp | xargs ls -ls 2>&1 |
    grep -Ei 'no such file' > x.tmp
    awk '{print $4}' x.tmp |tr -d "':;"
else
    echo ""; echo "[green]DSL include files all found:[/]" | rich -p -
fi

echo ""

rm bad-includes.tmp x.tmp
#end
    

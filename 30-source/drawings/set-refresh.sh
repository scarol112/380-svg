#!/bin/bash

# Set the refresh interval in 380-032.js to a new value

if [[ "$1" =~ ^[0-9]+$ ]]; then

    sed -i.bkp "/const REFRESH_MS/s/^.*$/const REFRESH_MS = ${1};/" ../assets/380-032.js

    echo ""
    echo "[green]Refresh inteval set to $1.[/]" | rich -p -
    echo "[cyan]Refresh the web page. [/]" | rich -p -
    echo ""
else
    echo ""
    echo "[dark_orange]$0 <integer milliseconds>" | rich -p -
    echo "Sets the refresh interval in 380-032.js to a new value" | rich -p -
    echo ""
fi


# end

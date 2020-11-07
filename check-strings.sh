#!/bin/bash

# If we have a STDIN, use it, otherwise get one
if tty >/dev/null 2>&1; then
    TTY=$(tty)
else
    TTY=/dev/tty
fi

IFS=$'\n'

check_file() {
    local file=$1
    local match_pattern=$2

    check_changes $file $match_pattern # check staged changes, cancel commit if found
    check_everything $file $match_pattern # check entire file, print info if found
}

check_changes() {
    local file=$1
    local match_pattern=$2

    local file_changes_with_context=$(git diff -U999999999 -p --cached --color=always -- $file)

    # From the diff, get the green lines starting with '+' and including '$match_pattern'
    local matched_additions=$(echo "$file_changes_with_context" | grep --color=always -C4 $'^\e\\[32m\+.*'"$match_pattern")

    if [ -n "$matched_additions" ]; then
        echo -e "\n$file additions match '$match_pattern':\n"

        for matched_line in $matched_additions
        do
            echo "$matched_line"
        done

        echo -e "\n\e[1;31mNot committing, because $file matches $match_pattern\e[0m"
        exit 1
    fi
}

check_everything() {
    local file=$1
    local match_pattern=$2

    local matched_old=$(cat "$file" | grep --color=always -C4 "$match_pattern")

    if [ -n "$matched_old" ]; then
        echo -e "\n$file old match '$match_pattern':\n"

        for matched_line in $matched_old
        do
            echo "$matched_line"
        done

        echo -e "\n\e[1;33mFound matches in older commits were $file matches $match_pattern\e[0m"
    fi
}

old_ifs=$IFS
IFS=,
MATCH='# TODO,# Todo,# todo,# DEBUG,# Debug,# debug'

for file in "$@"; do
    for match_pattern in $MATCH; do
        check_file $file $match_pattern
    done
done

IFS=$old_ifs
exit

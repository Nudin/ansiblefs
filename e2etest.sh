#!/usr/bin/env bash

vault_dir="test_vault"
mountpoint="test"

c=0

function echo_red() {
		echo -e "\e[31m$*\e[0m"
}
function echo_green() {
		echo -e "\e[32m$*\e[0m"
}

function failed() {
	if [[ "$2" != "" ]]; then
		echo_red "$1 failed:"
		echo "$2" | sed 's/.* echo: //'
	else
		echo_red "$1 failed"
	fi
	echo
	((c++))
}

function succeed() {
	echo_green "$1 succeed"
	echo
}

# mount
umount $mountpoint 2>/dev/null || :
./ansiblefs.py "$vault_dir" -opassword=a $mountpoint && succeed "mount" || failed "mount"
sleep 0.1

# Dir works
test "$(find $mountpoint | wc -l)"  == 2 || failed "Dir" "$(ls $mountpoint)"

# Read existent
old_txt="Testfile Nr1"
existent_file="$mountpoint/test.yml"
read_existent=$(cat $existent_file)
test "$read_existent" == "$old_txt" || failed "read" "$read_existent"

# Write to existent
teststring="teststring"
out=$(echo "$teststring" 2>&1 > "$existent_file") || failed "write to existent file" "$out"

# Read new content and restore old
read_existent=$(cat "$existent_file")
test "$read_existent" == "$teststring" \
	&& echo "$old_txt" 2>&1 > "$existent_file" \
	|| failed "read updated" "$read_existent"

# Write to new
new_file="$mountpoint/new.yml"
teststring="teststring"
out=$(echo "$teststring" 2>&1 > "$new_file") || failed "write" "$out"

# Read new
read_new=$(cat $new_file)
test "$read_new" == "$teststring" || failed "read" "$read_new"

# Delete (new) file
rm "$new_file" || failed "delete file"

# unmount
sleep 0.1
umount $mountpoint || failed "umount"
if [[ $c -ne 0 ]]; then
	echo_red "$c tests failed"
else
	echo_green "$c tests failed"
fi
exit $c

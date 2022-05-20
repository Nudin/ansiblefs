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

function print_result() {
	if [[ $? -eq 0 ]]; then
		succeed "$1"
	else
		failed "$1" "$2"
	fi
	return $?
}

trap 'cp "${existent_file_raw}.bk" "$existent_file_raw"; umount $mountpoint' EXIT


# Optional clean log file
if [[ "$1" == "--clear-log" ]]; then
	true > ansiblefs.log
fi

# mount
echo -e "\nmount" >> ansiblefs.log
umount $mountpoint 2>/dev/null || :
./ansiblefs.py "$vault_dir" -opassword=a $mountpoint; print_result "mount"
sleep 0.1

# Dir works
echo -e "\nDir works" >> ansiblefs.log
test "$(find $mountpoint | wc -l)"  == 2; print_result "Dir" "$(ls $mountpoint)"

# Read existent
echo -e "\nRead existent" >> ansiblefs.log
old_txt="Testfile Nr1"
existent_file="$mountpoint/test2.yml"
existent_file_raw="$vault_dir/test2.yml"
read_existent=$(cat $existent_file)
test "$read_existent" == "$old_txt"; print_result "read" "$read_existent"

# Write to existent
echo -e "\nWrite to existent" >> ansiblefs.log
teststring="teststring"
out=$(echo -n "$teststring" 2>&1 > "$existent_file"); print_result "write to existent file" "$out"

# Append to existent
echo -e "\nAppend to existent" >> ansiblefs.log
teststring="teststring"
out=$(echo -n "$teststring" 2>&1 >> "$existent_file"); print_result "append to existent file" "$out"

# Read new content and then restore old
echo -e "\nRead new content" >> ansiblefs.log
out=$(cat "$existent_file")
test "$out" == "$teststring$teststring"
print_result "read updated" "$out" "$out"
cp "${existent_file_raw}.bk" "$existent_file_raw"

# Write to new
echo -e "\nWrite to new" >> ansiblefs.log
new_file="$mountpoint/new.yml"
teststring="teststring"
out=$(echo "$teststring" 2>&1 > "$new_file"); print_result "write" "$out"

# Read new
echo -e "\nRead new" >> ansiblefs.log
read_new=$(cat $new_file)
test "$read_new" == "$teststring"; print_result "read" "$read_new"

# Delete (new) file
echo -e "\nDelete (new) file" >> ansiblefs.log
rm "$new_file"; print_result "delete file"

if [[ $c -ne 0 ]]; then
	echo_red "$c tests failed"
else
	echo_green "$c tests failed"
fi
exit $c

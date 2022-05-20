ansiblefs – mount your ansible vaults
=====================================

With ansiblefs you can mount a directories containing ansible vault files, and
will see them unencrypted on the mountpoint. This allows you to use the common
terminal commands like `cat`, `grep`, `rg`, `sed`, `awk` just as if the files
where unencrypted.

Usage
-----
```
$ ./ansiblefs.py vault_directory -opassword=YOURPASSWORD mountpoint
```

Limitation
----------
This more a hack then a fully featured file system. You can walk the file
structure and read and write to files, append to files and create new files.
Features like truncate, sparse files, etc. are not supported.

Security Implications
---------------------
Obviously when mounted every application with proper file rights can read the
content. If this decreases you security depends on your setup and especially to
how you currently work with vaults.
The unencrypted data is not saved to disk. However in the case that the memory
gets full, the kernel might write it to swap.
If the vaults contain very sensitive data you might consider using mount
namespaces to restrict access to the plain text files.

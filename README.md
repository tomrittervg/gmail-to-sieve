gmail-to-sieve
==============

A script to convert Gmail Filters into sieve filters for use with Dovecot.

Outputs two files. The first is your sieve rules. The second you must run in your .maildir to construct the folders. You will probably need to edit the chown at the end of the second file to match the corrcet owner.

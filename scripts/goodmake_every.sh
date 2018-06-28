#! /usr/local/bin/goodmake /bin/sh -se

# Build stanzas to repeat builds after time or events

############################################

#! default
    echo "No default period"

############################################

#! .day
    period='yesterday'

#! .hour
    period='-1 hour'

#! .day .hour
    touch -d "$period" .$1_ago
    [ $1 -nt .$1_ago ] || date>$1
    rm $1_ago

#! .os_install
    date -r /var/log/installer/syslog > $1

#? !.reboot
    $0 /dev/shm/reboot-timestamp

#? /dev/shm/reboot-timestamp
    # /dev/shm is blown away every reboot
    uptime=$(shell cut --fields 1 --delimiter ' ' < /proc/uptime)
    date -d "${uptime} seconds ago" >$1

############################################

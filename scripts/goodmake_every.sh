#! /usr/local/bin/goodmake /bin/sh -se

# Build stanzas to repeat builds after time or events

############################################

#! default
    echo "No default period"

############################################

#! .minute .hour .day .week .month .year
    period=${1#.}
    touch -d "1 $period ago" $1.ago
    [ $1 -nt $1.ago ] || date>$1
    rm $1.ago

#! .os_install .install
    date -r /var/log/installer/syslog > $1

#? !.reboot !.boot
    $0 /dev/shm/reboot-timestamp

#? /dev/shm/reboot-timestamp
    # /dev/shm is blown away every reboot
    uptime=$(cut --fields 1 --delimiter ' ' < /proc/uptime)
    date -d "${uptime} seconds ago" >$1

############################################

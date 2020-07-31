http --auth admin:otz http://172.17.0.2:5984/otz/$1 | jq -r ".title"
http --auth admin:otz http://172.17.0.2:5984/otz/$1 | jq -r ".text" | fold -s -w $(tput cols)

http --auth admin:otz http://172.17.0.2:5984/otz/$1 | jq -r ".images[0]" | base64 -d | kitty +kitten icat && \
http --auth admin:otz http://172.17.0.2:5984/otz/$1 | jq -r ".images[1]" | base64 -d | kitty +kitten icat && \
http --auth admin:otz http://172.17.0.2:5984/otz/$1 | jq -r ".images[2]" | base64 -d | kitty +kitten icat && \
http --auth admin:otz http://172.17.0.2:5984/otz/$1 | jq -r ".images[3]" | base64 -d | kitty +kitten icat && \
http --auth admin:otz http://172.17.0.2:5984/otz/$1 | jq -r ".images[4]" | base64 -d | kitty +kitten icat && \
http --auth admin:otz http://172.17.0.2:5984/otz/$1 | jq -r ".images[5]" | base64 -d | kitty +kitten icat && \
http --auth admin:otz http://172.17.0.2:5984/otz/$1 | jq -r ".images[6]" | base64 -d | kitty +kitten icat && \
http --auth admin:otz http://172.17.0.2:5984/otz/$1 | jq -r ".images[7]" | base64 -d | kitty +kitten icat && \
http --auth admin:otz http://172.17.0.2:5984/otz/$1 | jq -r ".images[8]" | base64 -d | kitty +kitten icat && \
http --auth admin:otz http://172.17.0.2:5984/otz/$1 | jq -r ".images[9]" | base64 -d | kitty +kitten icat && \
echo "Noch mehr Bilder…"

tpdf=$(tempfile)
http --auth admin:otz http://172.17.0.2:5984/otz/$1 | jq -r ".pdf" | base64 -d > $tpdf
xreader $tpdf
rm $tpdf

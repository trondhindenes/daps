# DAPS
## What is this
dapr.io is awesome, but has some weak spots around lifecycle management. Daps attempts to fix some of these.

## What DAPS does
### Startup robustness

### Shutdown coordination




```
# https://github.com/surajssd/self-signed-cert#install
self-signed-cert --namespace daps-system --service-name daps-webhook

# copy generated keys from temp dir into this repo's "keys" dir
kubectl --namespace=daps-system create secret tls webhook-certs --cert=keys/server.crt --key=keys/server.key

# this is the ca bundle for the webhook
openssl base64 -A < "keys/ca.crt"
```


```
docker build -t trondhindenes/daps-webhook .
docker build -f Dockerfile_sidecar -t trondhindenes/daps-sidecar .

docker push trondhindenes/daps-webhook
docker push trondhindenes/daps-sidecar
```
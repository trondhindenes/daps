


```

# https://github.com/surajssd/self-signed-cert#install
self-signed-cert --namespace daps-system --service-name daps-webhook

kubectl --namespace=daps-system create secret tls webhook-certs --cert=keys/server.crt --key=keys/server.key

# this is the ca bundle for the webhook
openssl base64 -A < "keys/ca.crt"
```


```
docker build -t daps .
docker build -f Dockerfile_sidecar -t daps-sidecar .

```
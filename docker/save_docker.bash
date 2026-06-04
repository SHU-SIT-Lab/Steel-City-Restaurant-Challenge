export CONTAINER_ID=`docker ps -lq`
docker commit $CONTAINER_ID aung9htet/ubuntu-22.04:jammy
echo "done"

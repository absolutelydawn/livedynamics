build:
	docker build -t front .

run:
	docker run -it -d --init -p 8000:8000 --name front front

exec:
	docker exec -it front /bin/bash

logs:
	docker logs front

ps:
	docker ps -a

img:
	docker images

rm:
	docker stop $$(docker ps -aq) && docker rm -f $$(docker ps -aq)

rmi:
	docker rmi $$(docker images -q)

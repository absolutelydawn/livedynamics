# Step 1 : Base Image
FROM node:16.20.2

# Step 2 : Package Install
RUN apt -y update && apt -y upgrade && apt -y install git net-tools vim

# Step 3 : Specify a working directory
WORKDIR /app

# Step 4 : Copy application files
COPY . .

# Step 5 : Install dependencies
RUN npm init -y
RUN npm install
RUN npm install -g nodemon

# Step 6 : Open port
EXPOSE 8000

# Step 7 : Execution Program
CMD ["nodemon", "app.js"]
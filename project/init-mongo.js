db = db.getSiblingDB('admin');

db.createUser({
  user: "root",
  pwd: "1234",
  roles: [ { role: "root", db: "admin" } ]
});

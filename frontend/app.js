const express = require('express');
const path = require('path');
const bodyParser = require('body-parser');
const mainRouter = require('./routes/main');
const env = require('dotenv').config({ path: '../.env' });

const app = express();

// 정적 파일 서빙
app.use(express.static(path.join(__dirname, 'public')));

// Body parser 설정
app.use(bodyParser.json());
app.use(bodyParser.urlencoded({ extended: false }));
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// 라우터 사용
app.use('/', mainRouter);

const PORT = process.env.PORT || 8000;
app.listen(PORT, () => {
    console.log(`Server is running on port ${PORT}`);
});

module.exports = app;

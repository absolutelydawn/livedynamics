const express = require('express');
const app = express();
const bodyParser = require('body-parser');
const fs = require('fs');
const path = require('path');
const multer = require('multer');
const env = require('dotenv').config({ path: '.env' });

app.use(bodyParser.json());
app.use(bodyParser.urlencoded({ extended: false }));
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

const AWS = require('aws-sdk');
const ID = process.env.ID;
const SECRET = process.env.SECRET;
const BUCKET_NAME = 'kibwa15';
const MYREGION = 'ap-northeast-2';
const s3 = new AWS.S3({ accessKeyId: ID, secretAccessKey: SECRET, region: MYREGION });

// Multer 설정
const upload = multer({ dest: 'uploads/' });

// 파일 업로드 라우트
app.post('/upload', upload.single('file'), (req, res) => {
    const fileContent = fs.readFileSync(req.file.path);
    const params = {
        Bucket: BUCKET_NAME,
        Key: `uploadedVideos/${req.file.originalname}`, // 원본 영상 업로드 경로 : uploadedVideos/
        Body: fileContent
    };
    s3.upload(params, (err, data) => {
        if (err) throw err;
        fs.unlinkSync(req.file.path); // 로컬에 저장된 파일 삭제
        res.send(`<script>alert("업로드가 성공하였습니다."); window.location.href = "/";</script>`);
    });
});

// 파일 목록 조회 라우트
app.get('/list', (req, res) => {
    var params = {
        Bucket: BUCKET_NAME,
        Delimiter: '/',
        Prefix: 'uploadedVideos/', 
    };
    s3.listObjects(params, function (err, data) {
        if (err) throw err;
        var fileList = data.Contents.map(item => ({
            key: item.Key,
            url: `https://${BUCKET_NAME}.s3.${MYREGION}.amazonaws.com/${item.Key}`
        }));
        res.json(fileList);
    });
});

// // 파일 다운로드 라우트 (Read) : download가 아니라 다른이름으로 바꾸기
// app.get('/downloadFile', (req, res) => {
//     const params = {
//         Bucket: BUCKET_NAME,
//         Key: req.query.key
//     };
//     s3.getObject(params, (err, data) => {
//         if (err) throw err;
//         res.attachment(req.query.key);
//         res.send(data.Body);
//     });
// });

// 파일 삭제 라우트 (Delete)
app.post('/deleteFile', (req, res) => {
    const params = {
        Bucket: BUCKET_NAME,
        Key: req.body.dlKey
    };
    s3.deleteObject(params, (err, data) => {
        if (err) throw err;
        res.send({ success: true });
    });
});

app.use(express.static('public'));

module.exports = app;

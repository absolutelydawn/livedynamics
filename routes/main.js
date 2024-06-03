const express = require('express');
const app = express();
const bodyParser = require('body-parser');
const fs = require('fs');
const path = require('path');
const multer = require('multer');
const env = require('dotenv').config({ path: '../.env' });

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
        Key: `uploadedVideos/${req.file.originalname}`, // 업로드할 폴더 경로 수정
        Body: fileContent
    };
    s3.upload(params, (err, data) => {
        if (err) throw err;
        fs.unlinkSync(req.file.path); // 로컬에 저장된 파일 삭제
        res.redirect('/list');
    });
});

// 파일 목록 조회 라우트
app.get('/list', (req, res) => {
    var params = {
        Bucket: BUCKET_NAME,
        Delimiter: '/',
        Prefix: 'uploadedVideos/', // 파일 목록 조회 폴더 경로 수정
    };
    s3.listObjects(params, function (err, data) {
        if (err) throw err;
        res.writeHead(200);
        var template = `
            <!doctype html>
            <html>
            <head>
                <title>Result</title>
                <meta charset="utf-8">
            </head>
            <body>
                <form ref='uploadForm' id='uploadForm' action='/upload' method='post' encType="multipart/form-data">
                    <input type="file" name="file" />
                    <input type='submit' value='Upload!' />
                </form>
                <table border="1" margin: auto; text-align: center;>
                    <tr>
                        <th> Key </th>
                        <th> LastModified </th>
                        <th> Size </th>
                        <th> StorageClass </th>
                        <th> Down </th>
                        <th> Del </th>
                    </tr>
        `;
        for (var i = 1; i < data.Contents.length; i++) {
        template += `
                    <tr>
                        <th> ${data.Contents[i]['Key']} </th>
                        <th> ${data.Contents[i]['LastModified']} </th>
                        <th> ${data.Contents[i]['Size']} </th>
                        <th> ${data.Contents[i]['StorageClass']} </th>
                        <th> 
                            <form method='post' action='downloadFile'>
                            <button type='submit' name='dlKey' value=${data.Contents[i]['Key']}>Down</button>
                            </form>
                        </th>
                        <th> 
                            <form method='post' action='deleteFile'>
                            <button type='submit' name='dlKey' value=${data.Contents[i]['Key']}>Del</button>
                            </form>
                        </th>
                    </tr>
            `;
        }
        template += `
                </table>
            </body>
            </html>
            `;
        res.end(template);
    });
});

// 파일 다운로드 라우트 (Read)
app.post('/downloadFile', (req, res) => {
    const params = {
        Bucket: BUCKET_NAME,
        Key: req.body.dlKey
    };
    s3.getObject(params, (err, data) => {
        if (err) throw err;
        res.attachment(req.body.dlKey);
        res.send(data.Body);
    });
});

// 파일 삭제 라우트 (Delete)
app.post('/deleteFile', (req, res) => {
    const params = {
        Bucket: BUCKET_NAME,
        Key: req.body.dlKey
    };
    s3.deleteObject(params, (err, data) => {
        if (err) throw err;
        res.redirect('/list');
    });
});

module.exports = app;

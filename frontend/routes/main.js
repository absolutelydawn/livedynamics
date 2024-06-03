const express = require('express');
const path = require('path');
const fs = require('fs');
const multer = require('multer');
const AWS = require('aws-sdk');
const router = express.Router();
const env = require('dotenv').config({ path: '../.env' });

// Multer 설정
const upload = multer({ dest: 'uploads/' });

const ID = process.env.ID;
const SECRET = process.env.SECRET;
const BUCKET_NAME = 'kibwa15';
const MYREGION = 'ap-northeast-2';
const s3 = new AWS.S3({ accessKeyId: ID, secretAccessKey: SECRET, region: MYREGION });

// 기존 라우트
router.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, '..', 'public', 'index.html'));
});

// 새로운 페이지 라우트
router.get('/edit', (req, res) => {
    res.sendFile(path.join(__dirname, '..', 'public', 'edit.html'));
});

router.get('/report', (req, res) => {
    res.sendFile(path.join(__dirname, '..', 'public', 'report.html'));
});

router.get('/tracking', (req, res) => {
    res.sendFile(path.join(__dirname, '..', 'public', 'tracking.html'));
});

// 파일 업로드 라우트
router.post('/upload', upload.single('file'), (req, res) => {
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
router.get('/list', (req, res) => {
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

// 파일 삭제 라우트 (Delete)
router.post('/deleteFile', (req, res) => {
    const params = {
        Bucket: BUCKET_NAME,
        Key: req.body.dlKey
    };
    s3.deleteObject(params, (err, data) => {
        if (err) throw err;
        res.send({ success: true });
    });
});

module.exports = router;

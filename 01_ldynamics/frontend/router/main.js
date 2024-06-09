const express = require('express');
const path = require('path');
const fs = require('fs');
const multer = require('multer');
const AWS = require('aws-sdk');
const router = express.Router();
const env = require('dotenv').config({ path: '../../.env' });

const upload = multer({ dest: 'uploads/' });

const ID = process.env.ID;
const SECRET = process.env.SECRET;
const BUCKET_NAME = 'kibwa15';
const MYREGION = 'ap-northeast-2';
const s3 = new AWS.S3({ accessKeyId: ID, secretAccessKey: SECRET, region: MYREGION });

router.get('/', (req, res) => {
    res.render('views');
});

router.post('/upload', upload.single('file'), (req, res) => {
    const fileContent = fs.readFileSync(req.file.path);
    const params = {
        Bucket: BUCKET_NAME,
        Key: `uploadedVideos/${req.file.originalname}`,
        Body: fileContent
    };
    s3.upload(params, (err, data) => {
        if (err) throw err;
        fs.unlinkSync(req.file.path);
        res.send('Success');
    });
});

router.get('/list', (req, res) => {
    const params = {
        Bucket: BUCKET_NAME,
        Delimiter: '/',
        Prefix: 'uploadedVideos/', 
    };
    s3.listObjects(params, (err, data) => {
        if (err) throw err;
        const fileList = data.Contents.map(item => ({
            key: item.Key,
            url: `https://${BUCKET_NAME}.s3.${MYREGION}.amazonaws.com/${item.Key}`
        }));
        res.json(fileList);
    });
});

router.get('/formerclips', (req, res) => {
    res.render('formerclips');
});

module.exports = router;

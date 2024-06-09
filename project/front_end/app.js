const express = require('express');
const axios = require('axios');
const path = require('path');

const app = express();
const PORT = 3000;

// 정적 파일 제공을 위한 설정
app.use(express.static('public'));

// 루트 경로에 접속했을 때 index.html을 제공
app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// 비디오 처리 요청을 보내는 라우트
app.get('/process-video', async (req, res) => {
    try {
        const response = await axios.post('http://15.164.180.50:8000/process-video/');
        res.send(response.data);
    } catch (error) {
        console.error('Error processing video:', error);
        res.status(500).send({ error: 'Failed to process video' });
    }
});

// 비디오 분할 및 업로드 요청을 보내는 라우트
app.post('/split-and-upload-video', async (req, res) => {
    try {
        const response = await axios.post('http://15.164.180.50:8000/split-and-upload-video/');
        res.send(response.data);
    } catch (error) {
        console.error('Error splitting and uploading video:', error);
        res.status(500).send({ error: 'Failed to split and upload video' });
    }
});

// 팀 데이터를 가져오는 라우트
app.get('/get-results', async (req, res) => {
    const team = req.query.team;
    try {
        const response = await axios.get(`http://15.164.180.50:8000/get-results?team=${team}`);
        res.send(response.data);
    } catch (error) {
        console.error('Error fetching team data:', error);
        res.status(500).send({ error: 'Failed to fetch team data' });
    }
});

app.listen(PORT, () => {
    console.log(`Server is running on http://15.164.180.50:${PORT}`);
});

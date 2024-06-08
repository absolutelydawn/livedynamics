const express = require('express');
const axios = require('axios');
const path = require('path');

const app = express();
const PORT = 3000;

app.use(express.static('public'));

app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.get('/process-video', async (req, res) => {
    try {
        const response = await axios.post('http://15.164.180.50:8000/process-video/');
        res.send(response.data);
    } catch (error) {
        res.status(500).send({ error: 'Failed to process video' });
    }
});

app.listen(PORT, () => {
    console.log(`Server is running on http://15.164.180.50:${PORT}`);
});

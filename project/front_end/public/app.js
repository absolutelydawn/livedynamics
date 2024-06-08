document.getElementById('process-video-button').addEventListener('click', async () => {
    try {
        const response = await axios.get('/process-video');
        document.getElementById('result').innerText = 'Video processing completed: ' + response.data.message;
    } catch (error) {
        console.error('Error processing video:', error);
        document.getElementById('result').innerText = 'Error processing video: ' + (error.response ? error.response.data.error : error.message);
    }
});
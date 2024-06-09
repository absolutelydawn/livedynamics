import logging
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import boto3
import cv2
import easyocr
from pymongo import MongoClient, errors
from dotenv import load_dotenv
import subprocess
from tempfile import NamedTemporaryFile
import tempfile
import asyncio

# 설정 로그
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI()

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f'WebSocket 연결됨: {websocket.client.host}:{websocket.client.port}')

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info(f'WebSocket 연결 종료: {websocket.client.host}:{websocket.client.port}')

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

# 비동기 로그 핸들러
class AsyncWebSocketHandler(logging.Handler):
    def __init__(self):
        super().__init__()

    async def async_emit(self, record):
        message = self.format(record)
        await manager.broadcast(message)

    def emit(self, record):
        asyncio.create_task(self.async_emit(record))

# 로그 핸들러 설정
logger.addHandler(AsyncWebSocketHandler())
logger.setLevel(logging.INFO)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 환경 변수 로드
load_dotenv()

# MongoDB 설정
mongo_uri = os.getenv('MONGO_URI')
client = MongoClient(mongo_uri)

db = client['ocr']
prior_data = db['prior_data']

# MongoDB 연결 테스트
try:
    client.admin.command('ping')
    logger.info("MongoDB 연결 성공")
except errors.ConnectionFailure:
    logger.error("MongoDB 연결 실패")

# AWS S3 설정
s3_client = boto3.client(
    's3',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    region_name=os.getenv('AWS_REGION')
)

BUCKET_NAME = os.getenv('AWS_S3_BUCKET')
S3_PATH = os.getenv('AWS_S3_PREFIX')
S3_UPLOAD_PATH = 'uploadedFiles/'
S3_OUTPUT_PATH = 'sepVideo/'

def calculate_histogram(image):
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1], None, [180, 256], [0, 180, 0, 256])
    cv2.normalize(hist, hist, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)
    return hist

def preprocess_image(image):
    scale_percent = 900
    width = int(image.shape[1] * scale_percent / 100)
    height = int(image.shape[0] * scale_percent / 100)
    dim = (width, height)
    resized = cv2.resize(image, dim, interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    enhanced = cv2.convertScaleAbs(binary, alpha=1.5, beta=0)
    return enhanced

def download_latest_s3_file(bucket_name, s3_path, download_path):
    response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=s3_path)
    if 'Contents' not in response:
        raise HTTPException(status_code=404, detail="No files found in S3 bucket.")
    files = response['Contents']
    latest_file = max(files, key=lambda x: x['LastModified'])
    latest_file_key = latest_file['Key']
    s3_client.download_file(bucket_name, latest_file_key, download_path)
    return latest_file_key

async def split_and_upload_video(input_file_path, output_prefix, segment_time, bucket_name, s3_path):
    # FFmpeg를 사용하여 비디오를 분할
    cmd = [
        'ffmpeg', '-i', input_file_path, '-c', 'copy', '-map', '0',
        '-segment_time', segment_time, '-f', 'segment',
        '-reset_timestamps', '1', f'{output_prefix}%03d.mp4'
    ]
    process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await process.communicate()

    if process.returncode == 0:
        logger.info("Video split process completed successfully.")
        for file in os.listdir('.'):
            if file.startswith(output_prefix) and file.endswith('.mp4'):
                s3_client.upload_file(file, bucket_name, f'{s3_path}{file}')
                logger.info(f"Uploaded {file} to s3://{bucket_name}/{s3_path}{file}")
                os.remove(file)
    else:
        logger.error(f"Error in video splitting process: {stderr.decode()}")

@app.get("/get-results")
async def get_results(team: str):
    try:
        results = prior_data.find_one({"team_name": team})
        if not results:
            raise HTTPException(status_code=404, detail="Team not found")
        return {
            "team_name": results["team_name"],
            "name": results["name"],
            "num": results["num"]
        }
    except Exception as e:
        logger.error(f'Error fetching results for team {team}: {str(e)}')
        raise HTTPException(status_code=500, detail="Failed to fetch results")

@app.get("/get-teams")
async def get_teams():
    try:
        teams = prior_data.distinct("team_name")
        return teams
    except Exception as e:
        logger.error(f'오류 발생: {str(e)}')
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # Keep the connection open
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.post("/split-and-upload-video/")
async def split_and_upload_video_endpoint():
    try:
        with NamedTemporaryFile(delete=False) as temp_file:
            temp_file_path = temp_file.name
            logger.info(f"S3에서 최신 파일을 {temp_file_path}로 다운로드")
            latest_file_key = download_latest_s3_file(BUCKET_NAME, S3_UPLOAD_PATH, temp_file_path)
            logger.info(f"S3에서 파일 다운로드 완료: {latest_file_key}")

        await split_and_upload_video(temp_file_path, "seg", "00:01:30", BUCKET_NAME, S3_OUTPUT_PATH)

        return {"message": "Video split and upload completed successfully"}

    except Exception as e:
        logger.error(f"오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/process-video/")
async def process_video():
    try:
        logger.info("비디오 처리 시작")
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file_path = temp_file.name
        logger.info(f"S3에서 최신 파일을 {temp_file_path}로 다운로드")
        latest_file_key = download_latest_s3_file(BUCKET_NAME, S3_PATH, temp_file_path)
        logger.info(f"S3에서 파일 다운로드 완료: {latest_file_key}")

        cap = cv2.VideoCapture(temp_file_path)
        frame_count = 0
        capture_count = 0
        capture_dir1 = './captures_team1'
        os.makedirs(capture_dir1, exist_ok=True)

        process_skip = 400
        frame_skip = 80
        threshold = 0.90
        name_counts = {}
        unique_data_count = 0

        fps = cap.get(cv2.CAP_PROP_FPS)
        logger.info(f"프레임 레이트: {fps}")

        template1 = cv2.imread('./template1.png')
        hist_template1 = calculate_histogram(template1)

        while True:
            ret, frame = cap.read()
            if not ret:
                logger.info("비디오 스트림의 끝에 도달")
                break
            frame_count += 1
            if frame_count % frame_skip != 0:
                continue

            roi_frame = frame[int(frame.shape[0] * 0.07):int(frame.shape[0] * 0.92),
                              int(frame.shape[1] * 0.215):int(frame.shape[1] * 0.574)]

            hist_roi = calculate_histogram(roi_frame)
            score1 = cv2.compareHist(hist_roi, hist_template1, cv2.HISTCMP_CORREL)
            logger.info(f'프레임 {frame_count}의 히스토그램 유사도 점수: {score1}')
            if score1 > threshold:
                capture_count += 1
                logger.info(f'프레임 {frame_count}에서 캡처 시작')
                capture_path = os.path.join(capture_dir1, f'capture_{capture_count}.png')

                ffmpeg_command = [
                    'ffmpeg', '-i', temp_file_path,
                    '-vf', f'select=eq(n\\,{frame_count})', '-vsync', 'vfr',
                    '-frames:v', '1', '-update', '1', capture_path
                ]
                logger.info(f'Running FFmpeg command: {ffmpeg_command}')

                process = subprocess.run(
                    ffmpeg_command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )

                if process.returncode != 0:
                    logger.error(f'FFmpeg 프로세스가 반환 코드 {process.returncode}로 실패')
                    continue

                # 파일이 정상적으로 생성되었는지 확인
                if not os.path.exists(capture_path):
                    logger.error(f"파일 {capture_path}이 존재하지 않음")
                    continue

                logger.info(f"프레임 {frame_count} 캡처 완료: {capture_path}")
                logger.info(f'점수1 : {score1}')

                logger.info('캡처한 이미지 읽기 중...')
                image = cv2.imread(capture_path)
                if image is None:
                    logger.error(f"파일 {capture_path}을(를) 읽을 수 없음")
                    continue

                height, width = image.shape[:2]
                roi_easyocr = image[int(height * 0.07):int(height * 0.92),
                                    int(width * 0.215):int(width * 0.574)]
                logger.info('OCR 진행 중...')
                roi_easyocr = preprocess_image(roi_easyocr)
                reader = easyocr.Reader(['ko', 'en'])
                result_easyocr = reader.readtext(roi_easyocr, detail=0)
                logger.info('OCR 완료')

                name_list = result_easyocr.copy()
                logger.info(f'이름 리스트 수: {len(name_list)}')

                if 'SUBSTITUTES' in name_list:
                    name_list.remove('SUBSTITUTES')

                logger.info(name_list)
                pname_list = []
                pnum_list = []
                team_name = name_list[0]

                for some in range(1, len(name_list)):
                    if some % 2 == 0:
                        pname_list.append(name_list[some])
                        logger.info(f'이름 목록 수: {len(pname_list)}')
                    else:
                        pnum_list.append(name_list[some])

                if len(pname_list) >= 10:
                    logger.info('작동 여부 테스트.')

                    key = (team_name, tuple(pname_list), tuple(pnum_list))
                    if key not in name_counts:
                        name_counts[key] = 1
                    else:
                        name_counts[key] += 1

                    if name_counts[key] == 2:
                        # 중복 확인
                        existing_doc = prior_data.find_one({
                            'team_name': team_name,
                            'name': pname_list,
                            'num': pnum_list
                        })
                        if existing_doc is None:
                            try:
                                prior_data.insert_one({
                                    'team_name': team_name,
                                    'name': pname_list,
                                    'num': pnum_list,
                                    'frame': frame_count
                                })
                                logger.info('DB 저장 성공')
                            except errors.PyMongoError as e:
                                logger.error(f'DB 저장 중 오류 발생: {str(e)}')
                        else:
                            logger.info('중복 데이터 발견, 저장하지 않음')

                        unique_data_count += 1
                        logger.info(f'고유 데이터 수: {unique_data_count}')
                        if unique_data_count >= 2:
                            logger.info("두 번의 고유 데이터 저장이 완료되었습니다. 프로세스를 종료합니다.")
                            break

        cap.release()
        os.remove(temp_file_path)
        return {"message": "Video processing completed successfully"}
    except Exception as e:
        logger.error(f'오류 발생: {str(e)}')
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)

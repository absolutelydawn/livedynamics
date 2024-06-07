from fastapi import FastAPI, HTTPException
import os
import boto3
import cv2
import ffmpeg
import uvicorn
import easyocr
from pymongo import MongoClient
from tempfile import NamedTemporaryFile
from dotenv import load_dotenv

app = FastAPI()

# Load environment variables
load_dotenv()

# MongoDB Setup
mongo_uri = os.getenv('MONGO_URI')
client = MongoClient(mongo_uri)
db = client['ocr']
prior_data = db['prior_data']

# AWS S3 Setup
s3_client = boto3.client(
    's3',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    region_name=os.getenv('AWS_REGION')
)

BUCKET_NAME = os.getenv('AWS_S3_BUCKET')
S3_PATH = os.getenv('AWS_S3_PREFIX')

# 히스토그램 템플릿 판별
def calculate_histogram(image):
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1], None, [180, 256], [0, 180, 0, 256])
    cv2.normalize(hist, hist, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)
    return hist

# 이미지 해상도 조정
def preprocess_image(image):
    scale_percent = 900  # Scale up by 900%
    width = int(image.shape[1] * scale_percent / 100)
    height = int(image.shape[0] * scale_percent / 100)
    dim = (width, height)
    resized = cv2.resize(image, dim, interpolation=cv2.INTER_CUBIC)

    # Grayscale, binary, contrast increase
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    enhanced = cv2.convertScaleAbs(binary, alpha=1.5, beta=0)

    return enhanced

# S3에서 최신 파일 다운로드
def download_latest_s3_file(bucket_name, s3_path, download_path):
    response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=s3_path)
    if 'Contents' not in response:
        raise HTTPException(status_code=404, detail="No files found in S3 bucket.")
    files = response['Contents']
    latest_file = max(files, key=lambda x: x['LastModified'])
    latest_file_key = latest_file['Key']
    s3_client.download_file(bucket_name, latest_file_key, download_path)
    return latest_file_key

# 비디오 처리 및 OCR
@app.post("/process-video/")
async def process_video():
    try:
        # S3에서 최신 파일 다운로드
        with NamedTemporaryFile(delete=False) as temp_file:
            temp_file_path = temp_file.name
            latest_file_key = download_latest_s3_file(BUCKET_NAME, S3_PATH, temp_file_path)
        
        cap = cv2.VideoCapture(temp_file_path)
        frame_count = 0
        capture_dir1 = './captures_team1'
        os.makedirs(capture_dir1, exist_ok=True)

        process_skip = 900
        frame_skip = 80
        threshold = 0.90
        name_counts = {}
        unique_data_count = 0

        fps = cap.get(cv2.CAP_PROP_FPS)
        print("프레임 레이트:", fps)

        template1 = cv2.imread('./template1.png')
        hist_template1 = calculate_histogram(template1)

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frame_count += 1
            if frame_count % frame_skip != 0:
                continue

            roi_frame = frame[int(frame.shape[0] * 0.07):int(frame.shape[0] * 0.92),
                              int(frame.shape[1] * 0.215):int(frame.shape[1] * 0.574)]

            hist_roi = calculate_histogram(roi_frame)
            score1 = cv2.compareHist(hist_roi, hist_template1, cv2.HISTCMP_CORREL)
            print('임계치 이상인지 판별중....')
            if score1 > threshold:
                print('영상 캡처중입니다...')
                capture_path = os.path.join(capture_dir1, f'capture_{frame_count}.png')
                
                # ffmpeg 명령 실행
                process = (
                    ffmpeg
                    .input(temp_file_path)
                    .filter('select', f'eq(n,{frame_count})')
                    .output(capture_path, vframes=1)
                    .run_async(pipe_stdout=True, pipe_stderr=True)
                )
                out, err = process.communicate()

                print(f'FFmpeg stdout: {out}')
                print(f'FFmpeg stderr: {err}')

                if process.returncode != 0:
                    print(f'FFmpeg process failed with return code {process.returncode}')
                    continue

                print(f"Captured frame {frame_count} at {capture_path}")
                print('score1 :', score1)

                print('캡처한 이미지를 읽는중....')
                image = cv2.imread(capture_path)
                if image is None:
                    print(f"File {capture_path} does not exist.")
                    continue

                # Set ROI
                height, width = image.shape[:2]
                roi_easyocr = image[int(height * 0.07):int(height * 0.92),
                                    int(width * 0.215):int(width * 0.574)]
                print('ocr 진행중입니다..')
                print('시간이 오래 소요될수 있습니다..')
                # Extract text using EasyOCR
                roi_easyocr = preprocess_image(roi_easyocr)
                reader = easyocr.Reader(['ko', 'en'])
                result_easyocr = reader.readtext(roi_easyocr, detail=0)
                print('ocr 완료..')

                name_list = result_easyocr.copy()

                print(f'Name list count: {len(name_list)}')

                if 'SUBSTITUTES' in name_list:
                    name_list.remove('SUBSTITUTES')

                print(name_list)
                pname_list = []
                pnum_list = []
                team_name = name_list[0]

                for some in range(1, len(name_list)):
                    if some % 2 == 0:
                        pname_list.append(name_list[some])
                        print(len(pname_list))
                    else:
                        pnum_list.append(name_list[some])

                if len(pname_list) == 11:
                    print('작동 여부 테스트.')

                    key = (team_name, tuple(pname_list), tuple(pnum_list))
                    if key not in name_counts:
                        name_counts[key] = 1
                    else:
                        name_counts[key] += 1

                    if name_counts[key] == 2:
                        prior_data.insert_one({
                            'team_name': team_name,
                            'name': pname_list,
                            'num': pnum_list,
                            'frame': frame_count
                        })
                        print('작동 여부 테스트.')

                        unique_data_count += 1
                        print(f"DB 저장 완료했습니다.!!")
                        print({key})

                        if unique_data_count >= 2:
                            print("두팀의 정보 저장 완료!!")
                            break
                        frame_count += process_skip  # 현재 위치에서 900 프레임 건너뛰기 설정
                        print('900프레임(30초)을 스킵합니다!!!')
                        print('다음 프레임 찾는중....')

        cap.release()
        os.remove(temp_file_path)
        return {"message": "Video processing completed"}
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

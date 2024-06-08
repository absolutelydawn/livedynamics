import cv2
import os
import ffmpeg
import easyocr
from pymongo import MongoClient

# MongoDB 설정
mongo_uri = os.getenv('MONGO_URI')
client = MongoClient(mongo_uri)
db = client['ocr']
prior_data = db['prior_data']

def calculate_histogram(image):
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1], None, [180, 256], [0, 180, 0, 256])
    cv2.normalize(hist, hist, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)
    return hist

def capture_frame(video_path, frame_number, output_path):
    try:
        out, err = (
            ffmpeg
            .input(video_path)
            .filter('select', f'eq(n,{frame_number})')
            .output(output_path, vframes=1)
            .run(capture_stdout=True, capture_stderr=True)
        )
        if os.path.exists(output_path):
            return True
        else:
            print(f"Failed to capture frame: {frame_number}, Error: {err.decode('utf8')}")
            return False
    except ffmpeg.Error as e:
        print(f"ffmpeg error: {e.stderr.decode('utf8')}")
        return False

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

template1 = cv2.imread('./template1.png')
hist_template1 = calculate_histogram(template1)

video_path = './k3_project_video.mp4'
cap = cv2.VideoCapture(video_path)

frame_count = 0
capture_dir1 = './captures_team1'
os.makedirs(capture_dir1, exist_ok=True)

process_skip = 500

frame_skip = 80
threshold = 0.90
name_counts = {}
unique_data_count = 0

fps = cap.get(cv2.CAP_PROP_FPS)
total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
print("프레임 레이트:", fps)
print("총 프레임 수:", total_frames)

skip_once = False

while True:
    ret, frame = cap.read()
    if not ret:
        break
    frame_count += 1
    if frame_count % frame_skip != 0:
        continue
    if skip_once:
        frame_count += process_skip
        skip_once = False
    if frame_count >= total_frames:
        print("프레임 범위를 초과했습니다.")
        break
    roi_frame = frame[int(frame.shape[0] * 0.07):int(frame.shape[0] * 0.92),
                      int(frame.shape[1] * 0.215):int(frame.shape[1] * 0.574)]
    
    hist_roi = calculate_histogram(roi_frame)
    score1 = cv2.compareHist(hist_roi, hist_template1, cv2.HISTCMP_CORREL)
    print('임계치 이상인지 판별중....')
    if score1 > threshold:
        print('영상 캡처중입니다...')
        capture_path = os.path.join(capture_dir1, f'capture_{frame_count}.png')
        if capture_frame(video_path, frame_count, capture_path):
            print(f"Captured frame {frame_count} at {capture_path}")
            print('score1 :', score1)
        else:
            print(f"Failed to capture frame {frame_count} at {capture_path}")
            continue
        
        print('캡처한 이미지를 읽는중....')
        if not os.path.exists(capture_path):
            print(f"File {capture_path} does not exist.")
            continue
        
        image = cv2.imread(capture_path)
        
        if image is None:
            print(f"Failed to read the image from {capture_path}")
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

            if name_counts[key] == 1:  # 처음 발견되었을 때 저장
                prior_data.insert_one({
                    'team_name': team_name,
                    'name': pname_list,
                    'num': pnum_list,
                    'frame': frame_count
                })
                print('DB 저장 완료했습니다.')
                unique_data_count += 1
                print(f'Unique data count: {unique_data_count}')
                skip_once = True
                frame_count += process_skip  # 현재 위치에서 900 프레임 건너뛰기 설정
                print('900프레임(30초)을 스킵합니다!!!')
                print('다음 프레임 찾는중....')

            if name_counts[key] >= 2:
                print("동일한 팀의 정보가 두 번 이상 저장되었습니다. 작업을 종료합니다.")
                break

cap.release()

# PIPEGUARD AI — 지하배관 지능형 이상 진단 시스템

**실시간 진동·알림 배포 시작:** 첨부 진동 모델, 센서 API, n8n 이메일 연결은 [START_HERE.md](START_HERE.md)를 먼저 확인하세요. 아래는 기존 기능 안내입니다.

CSV 특징값 또는 수동 주파수 → 학습 입력 검증 → 전처리 → 모델 판정 → SQLite 저장 → 대시보드 및 CSV 내보내기

원시 시계열 CSV → 센서 열 및 샘플링 주파수 선택 → 시간 파형 및 FFT

| 파일 | 역할 |
| --- | --- |
| `app.py` | 공통 화면, 사이드바 탐색, 모델 연결 상태 |
| `pages/dashboard.py` | 진단 건수, 최근 기록, 센서 그래프 |
| `pages/manual_diagnosis.py` | 단일 주파수 모델 진단 |
| `pages/csv_analysis.py` | 특징값 진단, 결과 다운로드, 원시 신호 시각화 |
| `pages/history.py` | SQLite 기록 조회, 필터, 다운로드 |
| `utils/model_loader.py` | 입력 계약 검사, RF·OCSVM 모델 추론 |
| `utils/preprocessing.py` | CSV 파싱 및 수치 검증 |
| `utils/visualization.py` | Plotly 그래프, SciPy FFT |
| `utils/database.py` | SQLite 생성과 저장 및 조회 |
| `training/train_model.py` | RF 학습, 테스트 평가 및 모델 저장 |
| `requirements.txt` | Python 의존성 |
| `.streamlit/config.toml` | 다크 테마와 로컬 서버 설정 |
| `models/` · `data/` | 학습 모델과 메타데이터 · 로컬 DB |

## Windows PowerShell에서 실행

ZIP을 풀고 VS Code에서 `pipeguard_ai` 폴더를 엽니다. PowerShell의 현재 폴더에 `app.py`와 `requirements.txt`가 있는지 확인합니다.

```powershell
py -3.13 --version
py -3.13 -m pip install -r requirements.txt
py -3.13 -m streamlit run app.py
```

브라우저에서 [http://localhost:8501](http://localhost:8501)을 엽니다. 종료하려면 PowerShell에서 Ctrl+C를 누릅니다. 8501이 사용 중이면 `--server.port 8502`를 실행 명령 뒤에 붙이고 브라우저에서 8502로 접속합니다.

최초 실행 시 대시보드에 **AI 모델 미연결**이 표시됩니다. 원시 신호 시각화는 모델과 독립적으로 사용할 수 있습니다.

## 실제 라벨 데이터로 RF 학습

CSV의 한 행은 측정 구간의 특징값입니다. 여러 행이 같은 .mat 파일이나 측정 세션에서 나온 경우 동일 그룹 ID를 지정하세요. 테스트 그룹은 학습 그룹에서 제외됩니다. 특징값이 같은 중복행은 제거하며, 같은 특징값에 서로 다른 그룹이나 라벨이 있으면 학습을 중지합니다. 독립 측정 행만 사용한다면 `--group source_file` 대신 `--independent-rows`를 사용하세요.

입력 형식 예시이며 특징명과 단위는 본인 학습 데이터에 맞게 바꾸세요.

```csv
source_file,frequency_khz,rms,label
capture_A.mat,35.5,0.02,정상
capture_B.mat,41.7,0.19,이상
```

두 행은 형식 설명용입니다. 양쪽 분할에 두 클래스가 남을 만큼 독립적인 실측 그룹을 제공해야 합니다.

```powershell
py -3.13 -m training.train_model data\labeled_features.csv --label label --group source_file --features frequency_khz rms --units kHz V
```

실제 라벨이 `0`과 `1`이면 `--normal 0 --anomaly 1`을 추가합니다. 평가 지표와 혼동행렬은 PowerShell에 출력됩니다. 모델과 메타데이터는 기본적으로 `models/`에 저장됩니다. 아래 명령은 주파수 한 개로 새 RF를 학습하고 수동 메뉴를 활성화하는 예시입니다.

```powershell
py -3.13 -m training.train_model data\labeled_features.csv --label label --group source_file --features frequency_khz --units kHz --manual-frequency
```

기존 모델을 보관하려면 별도 출력 경로에 학습한 뒤 연결할 모델만 `models/`에 복사하세요. 위 두 명령은 같은 기본 경로를 사용합니다.

## 기존 RF 또는 OCSVM 연결

직접 학습했거나 출처를 확인한 Joblib 파일을 사용하세요. `models/rf_model.joblib`과 `models/model_metadata.json`을 함께 배치합니다. 전처리기가 모델의 Pipeline에 포함되어 있다면 `external_preprocessor`는 `false`입니다. 별도 객체라면 `true`로 바꾸고 `models/preprocessor.joblib`을 추가하세요. 원래 학습 환경의 라이브러리 버전과 모델을 만든 환경의 커스텀 클래스도 맞춰야 합니다.

```json
{
  "model_name": "Random Forest",
  "model_version": "capstone-rf-1",
  "features": [
    {"name": "frequency_khz", "unit": "kHz"},
    {"name": "rms", "unit": "V"}
  ],
  "normal_label": 0,
  "anomaly_label": 1,
  "external_preprocessor": false,
  "input_type": "dataframe",
  "manual_frequency_feature": null
}
```

- `features`는 학습에 사용한 이름과 순서, 단위를 그대로 적습니다. 특징값 CSV의 숫자 단위는 업로드 전에 맞추세요. CSV 열의 물리 단위는 앱에서 자동 확인할 수 없습니다.
- `input_type`은 학습 당시 NumPy 배열을 입력했다면 `array`, 열 이름이 있는 DataFrame을 입력했다면 `dataframe`입니다.
- 주파수 한 개로 학습한 모델에서 수동 진단을 사용하려면 `manual_frequency_feature`에 해당 열 이름을 적고 단위를 `Hz` 또는 `kHz`로 설정합니다. UI 입력은 kHz이며 학습 단위가 Hz이면 앱이 변환합니다.
- OCSVM을 연결할 때도 이 앱의 모델 파일 경로는 `models/rf_model.joblib`입니다. 표준 OneClassSVM 출력을 사용하면 `normal_label`은 1, `anomaly_label`은 -1입니다. 결정 점수 표시가 필요하면 `"decision_score_label": "OCSVM 결정 점수 (음수는 이상)"`를 추가합니다. OCSVM 점수는 모델 확률 필드에 기록하지 않습니다.
- 새 파일을 넣은 뒤 페이지 새로고침이나 메뉴 이동으로 연결 상태를 갱신합니다. 모델을 갱신할 때 버전도 바꾸세요.

## 분석과 기록

1. **특징값 CSV 진단**에서 CSV를 올리면 미리보기와 결측치 요약이 표시됩니다. 모델이 연결되어 있으면 자동으로 검증하고 분석하며, 입력 특징값과 결과가 SQLite에 저장됩니다.
2. **원시 시계열 시각화**에서 등간격 원시 샘플 CSV를 올리고 센서 열과 실제 샘플링 주파수(Hz)를 입력합니다. 4~250,000개 샘플을 지원합니다. 시간 파형은 화면 표시용으로 일부 점을 샘플링하고 FFT는 선택 구간 전체를 계산합니다.
3. **진단 기록**에서 판정별 조회와 CSV 다운로드를 할 수 있습니다. 기록은 `data/diagnoses.sqlite3`에 저장됩니다. Excel 한글 표시를 위해 CSV는 UTF-8 BOM으로 저장됩니다.

RF 결과의 정상·이상은 모델이 출력한 클래스입니다. 이상 확률은 RF의 이상 클래스 예측값이며 실제 배관의 고장 확률로 별도 보정한 값은 아닙니다. 특징값별 영향도나 결함 위치는 현재 화면에서 추정하지 않습니다.

## 캡스톤 노트북 OCSVM 연결

`캡스톤_데이터분석_전체과정_통합_20261108_v2(3).ipynb`의 OCSVM 학습 셀이 저장하는 `config.json`, 선택한 폴드의 `<특징세트>_fold<N>_scaler.joblib` 및 `<특징세트>_fold<N>_OCSVM.joblib`을 `models/capstone_ocsvm/`에 복사합니다. 본인이 생성했거나 출처를 확인한 Joblib 파일을 사용하세요. 세 파일은 같은 실행 결과에서 가져오세요.

사이드바 **캡스톤 OCSVM**에서 특징 세트와 폴드를 선택하고 해당 특징값 CSV를 올립니다. `v1_raw28`은 `leak_features_candidate_600x28.csv`, `v2_core24`와 `v2_plus28`은 `v2_features_600.csv`를 사용합니다. CSV는 로그 및 스케일링 적용 전 특징값이어야 합니다. 앱은 노트북의 열 순서, 로그 변환, 학습된 RobustScaler, float32 변환 및 `-score_samples`를 재현합니다. 배치마다 한 행당 하나의 희소도 점수를 표시합니다. 점수는 기존 RF의 정상·이상 통계와 SQLite 판정 기록에 합산하지 않습니다.

`task03_index_전달용.zip`에는 측정 파일 인덱스와 분할표가 있습니다. 이 파일은 모델 파일이나 입력 특징값 CSV로 사용할 수 없습니다. 기존 단일 RF 연결과 RF 학습 메뉴용 스크립트는 위 설명을 따릅니다. 프로젝트 고유의 1·2단계 RF를 연결하려면 해당 모델 파일, 입력 전처리 코드와 단계별 판정 규칙이 필요합니다.

### 저장된 OCSVM이 없을 때

이번에 첨부한 `캡스톤_데이터분석_전체과정_통합_20261108_v2 (1).ipynb`의 OCSVM 학습·점수 계산에서 필요한 부분을 추출했습니다. 아래처럼 노트북의 특징값 CSV와 **같은 폴드**의 `fold0_file_roles.csv`가 있으면 OCSVM과 스케일러를 다시 생성할 수 있습니다. 원시 MAT 가공을 마친 CSV가 필요합니다.

```powershell
python -m training.train_capstone_ocsvm v2_features_600.csv fold0_file_roles.csv --candidate v2_core24 --fold 0
```

특징 세트와 파일이 다르면 인자를 바꾸세요. `v1_raw28`에는 `leak_features_candidate_600x28.csv`를 사용합니다. 학습은 폴드의 train 행만 사용하며 결과는 `models/capstone_ocsvm/`에 저장됩니다. 첨부 노트북의 분류 데이터 준비 셀에는 정상·균열 데이터 목록을 구성하는 코드가 있습니다. 프로젝트 고유 RF의 학습, 추론, 단계 전환 코드는 확인되지 않았습니다.

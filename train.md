# 抽帧
python -u preprocess_dataset.py \
    --checkpoints_dir ./pretrained_models \
    --name face_recon_feat0.2_augment \
    --epoch=[epoch] \
    --use_opengl False \
    --bfm_folder ./pretrained_models/BFM \
    --video_dir [video_dir] \
    --result_dir ./tmp/preprocessed_dataset
# 打标签
python -u preprocess_dataset_extra.py  --root_dir ./tmp/preprocessed_dataset --face_list ./tmp/preprocessed_dataset/mylist.txt
# 改参数
python -u update_config.py \
    --batch_size [batch_size|2] \
    --num_workers [num_workers|4] \
    --max_steps [max_steps|2000] \
    --lr [lr|2e-5] \
    --min_lr [min_lr|1e-5] \
    --checkpoint_interval [checkpoint_interval|500]

# 训练
accelerate launch --main_process_port 29501 --config_file config/accelerate_config.yaml train_joygen.py
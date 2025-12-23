import yaml
import argparse
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Update joygen.yaml parameters")
    parser.add_argument('--batch_size', type=int, help='Dataset batch size')
    parser.add_argument('--num_workers', type=int, help='Dataset num_workers')
    parser.add_argument('--max_steps', type=int, help='Optimizer max_steps')
    parser.add_argument('--lr', type=float, help='Optimizer learning rate')
    parser.add_argument('--min_lr', type=float, help='Optimizer min_lr')
    parser.add_argument('--checkpoint_interval', type=int, help='Checkpoint save interval')

    args = parser.parse_args()

    config_path = Path("config/joygen.yaml")
    if not config_path.exists():
        raise FileNotFoundError(f"{config_path} not found!")

    # 读取 YAML
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # 修改 dataset 参数
    if args.batch_size is not None:
        config['dataset']['batch_size'] = args.batch_size
    if args.num_workers is not None:
        config['dataset']['num_workers'] = args.num_workers

    # 修改 optimizer 参数
    if args.max_steps is not None:
        config['opti']['max_steps'] = args.max_steps
    if args.lr is not None:
        config['opti']['lr'] = args.lr
    if args.min_lr is not None:
        config['opti']['min_lr'] = args.min_lr

    # 修改 checkpoint 参数
    if args.checkpoint_interval is not None:
        config['checkpoint_save_interval'] = args.checkpoint_interval
        config['checkpoint_valiation_interval'] = args.checkpoint_interval

    # 保存 YAML
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, sort_keys=False)

    print("Config updated successfully!")

if __name__ == "__main__":
    main()

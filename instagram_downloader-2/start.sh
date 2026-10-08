#!/bin/bash
cd "$(dirname "$0")"

echo "========================================"
echo "  Instagram Downloader"
echo "========================================"
echo ""
echo "  1. Download from following list"
echo "  2. Get following list"
echo "  3. Download one profile"
echo "  4. Sort faces (1 / 2+ / none)"
echo "  5. Custom command"
echo "  0. Exit"
echo ""
read -p "Select (0-5): " choice

case "$choice" in
  1)
    read -p "List file name (ex: following_xxx.txt): " fname
    [ -z "$fname" ] && exit 0
    python3 instagram_downloader.py --from-file "$fname"
    ;;
  2)
    read -p "Instagram ID: " uid
    [ -z "$uid" ] && exit 0
    python3 instagram_downloader.py --following "$uid"
    ;;
  3)
    read -p "Instagram ID: " uid
    [ -z "$uid" ] && exit 0
    python3 instagram_downloader.py --profile "$uid"
    ;;
  4)
    python3 instagram_downloader.py --sort-faces
    ;;
  5)
    echo "Example: --from-file list.txt --max 30"
    echo "Example: --profile username --video"
    read -p "Arguments: " args
    [ -z "$args" ] && exit 0
    python3 instagram_downloader.py $args
    ;;
  *)
    exit 0
    ;;
esac

echo ""
echo "----------------------------------------"
read -p "Press Enter to exit..."

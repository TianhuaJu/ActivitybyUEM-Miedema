# 1. 创建或编辑 .gitignore 文件
echo "build/" >> .gitignore
echo "dist/" >> .gitignore
echo "*.pkg" >> .gitignore
echo "*.exe" >> .gitignore

# 2. 从 Git 中移除已追踪的构建文件
git rm --cached -r build/
git rm --cached -r dist/

# 3. 提交更改
git add .gitignore
git commit -m "Remove build files from version control"
git push
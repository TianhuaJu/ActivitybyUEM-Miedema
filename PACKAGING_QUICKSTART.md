# 🚀 打包快速入门

## 一键打包（推荐）

```bash
pyinstaller AlloyActApp_Optimized.spec
```

生成的程序位于: `dist/AlloyActApp/`

---

## ⚡ 性能对比

| 版本 | 启动时间 | 说明 |
|------|---------|------|
| ❌ Main.spec | 5-10秒 | onefile模式，需解压 |
| ⚠️ AlloyActApp.spec | 3-5秒 | 基础优化 |
| ✅ **AlloyActApp_Optimized.spec** | **1-2秒** | **推荐使用** |

---

## 🎯 主要优化点

1. ✅ **onedir模式** - 避免每次解压
2. ✅ **完整hiddenimports** - 避免运行时动态加载
3. ✅ **排除无用模块** - 减小体积，加快导入
4. ✅ **运行时钩子** - 优化启动配置
5. ✅ **关闭UPX** - 减少解压延迟

---

## 📦 构建流程

```bash
# 1. 清理旧构建（可选）
rm -rf build/ dist/

# 2. 打包
pyinstaller AlloyActApp_Optimized.spec

# 3. 测试
cd dist/AlloyActApp/
./AlloyActApp  # 或 AlloyActApp.exe (Windows)
```

---

## ❓ 常见问题

**Q: 首次启动还是慢？**
A: 杀毒软件在扫描，添加到白名单即可。

**Q: 打包后崩溃？**
A: 使用 `--console` 模式查看错误日志。

**Q: 想要单文件版本？**
A: 不推荐！会让启动时间回到5-10秒。

---

## 📚 详细文档

查看 [BUILD_GUIDE.md](BUILD_GUIDE.md) 获取完整说明。

---

**记住**: 使用 `AlloyActApp_Optimized.spec` = 启动快 5-10倍！ 🎉

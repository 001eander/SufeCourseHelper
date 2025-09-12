# SUFE 选课助手

$$
\textcolor{red}{
    本项目仅作为研究使用，请勿依赖本项目。选课相关事宜最终解释权归学校教务处所有。
}
$$

本人从学长那里得到了一份选课助手，一看是`exe`，Hex 编辑器再一看有`MEIPASS`，确定是 `pyinstaller` 打包的。

使用 [pyinstxtractor](https://github.com/extremecoders-re/pyinstxtractor) 提取出`pyc`文件，发现 python 版本是 3.11。

尝试使用 [uncompyle6](https://github.com/rocky/python-uncompyle6) 反编译，失败；尝试使用 [pylingual](https://pylingual.io/) 反编译，成功。

基于反编译代码，我重写了选课助手，选择[uv](https://docs.astral.sh/uv/)做包管理，更新了 log 系统，使用[toml](https://toml.io/en/)而非[json](https://www.json.org/json-en.html)作为配置文件，优化了选课逻辑。

如果你能看懂这份代码，那你肯定具备让它跑起来的能力；如果你看不懂，请联系能看懂的人。

## To Do

1. 添加根据课程序号自动获取课程ID的功能
2. 添加自动获取Cookie的功能
3. 赌！添加自动退掉不需要的课程然后选课的功能
4. 反反制，使用[selenium](https://www.selenium.dev)实现

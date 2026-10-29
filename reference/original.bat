@echo off
setlocal enabledelayedexpansion

REM Получаем имя текущего скрипта
set "script_name=%~nx0"

REM Создаём каталоги, если не существуют
md archives 2>nul
md iso 2>nul
md music 2>nul
md video 2>nul
md programs 2>nul
md photos 2>nul
md images 2>nul
md docs 2>nul

REM Архивы
for %%f in (*.zip *.gz *.tgz *.rar *.7z *.tar *.bz2 *.xz *.cab *.arj *.lzh *.ace *.001) do (
  if exist "%%f" if /I not "%%f"=="%script_name%" move "%%f" archives\
)

REM ISO-образы
for %%f in (*.iso *.img *.bin *.cue *.nrg *.mdf *.vcd *.dmg) do (
  if exist "%%f" if /I not "%%f"=="%script_name%" move "%%f" iso\
)

REM Видео
for %%f in (*.avi *.mov *.mp4 *.mkv *.3gp *.webm *.flv *.wmv *.mpeg *.mpg *.vob *.m4v *.ts *.mts *.divx *.f4v) do (
  if exist "%%f" if /I not "%%f"=="%script_name%" move "%%f" video\
)

REM Музыка
for %%f in (*.mp3 *.wav *.flac *.aac *.ogg *.wma *.m4a *.aiff *.alac *.ape *.pls *.m3u *.aimppl) do (
  if exist "%%f" if /I not "%%f"=="%script_name%" move "%%f" music\
)

REM Программы
for %%f in (*.exe *.msi *.apk *.dmg *.pkg *.app *.bat *.sh *.deb *.rpm *.jar *.py *.com *.cmd *.scr *.ps1) do (
  if exist "%%f" if /I not "%%f"=="%script_name%" move "%%f" programs\
)

REM Фото
for %%f in (*.jpg *.jpeg *.jpe *.heic *.cr2 *.nef *.arw *.dng *.raw *.orf *.rw2 *.srw *.tif *.tiff *.pef *.bay) do (
  if exist "%%f" if /I not "%%f"=="%script_name%" move "%%f" photos\
)

REM Изображения
for %%f in (*.png *.bmp *.gif *.tiff *.svg *.webp *.ico *.psd *.ai *.xcf *.emf *.wmf *.dds *.jpf *.jpx) do (
  if exist "%%f" if /I not "%%f"=="%script_name%" move "%%f" images\
)

REM Документы
for %%f in (*.pdf *.txt *.doc *.docx *.xls *.xlsx *.ods *.rtf *.odt *.ppt *.pptx *.csv *.djvu *.epub *.fb2 *.md *.tex *.log) do (
  if exist "%%f" if /I not "%%f"=="%script_name%" move "%%f" docs\
)

REM Удаляем торрент-файлы и magnet
del /Q *.torrent 2>nul
del /Q *.magnet 2>nul

endlocal

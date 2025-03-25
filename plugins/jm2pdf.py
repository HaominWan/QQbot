import jmcomic
import os
import glob
from PIL import Image
from jmcomic.jm_exception import *

async def get_pdf(code):
    try: 
        temp_dir = f"Bot/tmp/{code}"
        pdf_name = f"Bot/tmp/{code}/{code}.pdf"
        
        option = jmcomic.create_option_by_file("Bot\plugins\option.yml")
        jmcomic.download_album(code, option)
        
        # 获取所有图片并按数字顺序排序
        images = []
        image_files = glob.glob(os.path.join(temp_dir, "*.jpg")) #+ glob.glob(os.path.join(temp_dir, "*.png"))
        image_files.sort(key=lambda x: int(''.join(filter(str.isdigit, os.path.basename(x)))))
        
        # 打开第一张图片
        first_image = Image.open(image_files[0])
        
        # 转换所有其他图片
        other_images = []
        for img_path in image_files[1:]:
            img = Image.open(img_path)
            if img.mode == 'RGBA':
                img = img.convert('RGB')
            other_images.append(img)
        
        # 保存为PDF
        if first_image.mode == 'RGBA':
            first_image = first_image.convert('RGB')
        first_image.save(pdf_name, save_all=True, append_images=other_images)
        
        # 关闭所有图片
        first_image.close()
        for img in other_images:
            img.close()
        
        # 删除临时文件夹
        for file in image_files:
            os.remove(file)

        return pdf_name
    except MissingAlbumPhotoException as e:
        print(e)
        return 0
    except Exception as e:
        print(e)
        return 0

# if __name__ == "__main__":
#     import asyncio
#     async def main():
#         pdf_name = await get_pdf("432590")
#         print(pdf_name)
#     asyncio.run(main())
from PIL import Image
import numpy as np

class ImageHelper:

    def read_image(self, file, width = 300):
        # Resize image
        img = Image.open(file)
        if img.size[0] != width:
            scale = width / float(img.size[0])

            height = int((img.size[1] * scale))
            img = img.resize((width, height), Image.ANTIALIAS)

        # Convert to numpy
        image = np.array(img)
        image = image[:, :, :3]

        # Check that height is not less than width
        [h, w, _] = image.shape
        if h < w:
            to_add = np.ndarray([w-h, w, 3], dtype=np.uint8)
            to_add.fill(0)
            image = np.append(image, to_add, axis=0)

        return (image - 128.) / 128.

    def make_equal(self, imgs, max_height = 1200):
        max_h = 0
        for img in imgs:
            h, _, _ = np.shape(img)
            max_h = max(max_h, h)

        max_h = min(max_height, max_h)
        for i, img in enumerate(imgs):
            h, w, c = np.shape(img)
            if h == max_h:
                continue

            if h < max_h:
                to_add = np.zeros([max_h - h, w, c])
                imgs[i] = np.concatenate((img, to_add), axis=0)
            else:
                imgs[i] = img[:max_h, :, :]

        return imgs

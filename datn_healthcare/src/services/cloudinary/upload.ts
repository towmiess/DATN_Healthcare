export type CloudinaryUploadResult = {
  secure_url: string;
  public_id: string;
};

const getCloudinaryConfig = () => {
  const cloudName = import.meta.env.VITE_CLOUDINARY_CLOUD_NAME as string | undefined;
  const uploadPreset = import.meta.env.VITE_CLOUDINARY_UPLOAD_PRESET as string | undefined;

  if (!cloudName || !uploadPreset) {
    throw new Error("Missing Cloudinary config. Please set VITE_CLOUDINARY_CLOUD_NAME and VITE_CLOUDINARY_UPLOAD_PRESET.");
  }

  return { cloudName, uploadPreset };
};

export const uploadImageToCloudinary = async (file: File): Promise<CloudinaryUploadResult> => {
  const { cloudName, uploadPreset } = getCloudinaryConfig();

  const formData = new FormData();
  formData.append("file", file);
  formData.append("upload_preset", uploadPreset);

  const response = await fetch(`https://api.cloudinary.com/v1_1/${cloudName}/image/upload`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new Error(`Cloudinary upload failed with status ${response.status}`);
  }

  const data = (await response.json()) as CloudinaryUploadResult;
  if (!data?.secure_url) {
    throw new Error("Cloudinary response does not contain secure_url");
  }

  return data;
};

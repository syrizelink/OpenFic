import { Flex, Text } from "@radix-ui/themes";
import type { ReactNode } from "react";

interface IndexSettingsSectionHeaderProps {
  title: string;
  action?: ReactNode;
}

export function IndexSettingsSectionHeader({ title, action }: IndexSettingsSectionHeaderProps) {
  return (
    <Flex
      align="center"
      gap="3"
      wrap="wrap"
    >
      <Text
        size="2"
        weight="medium"
      >
        {title}
      </Text>
      {action}
    </Flex>
  );
}
